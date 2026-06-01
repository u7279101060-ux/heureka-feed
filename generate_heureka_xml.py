#!/usr/bin/env python3
"""
ARCHE Heureka XML feed generator.

Public Shopify endpoint (žádný token, žádná custom app).
Heureka 2026 spec (DELIVERY element, CATEGORYTEXT prefix).

Použití:
    python generate_heureka_xml.py

Env (přes GitHub Actions Variables nebo lokálně):
    SHOPIFY_SHOP           default: archefashion.com
    HEUREKA_CATEGORY_TEE   default: Móda | Pánská móda | Pánská trička a tílka
    HEUREKA_CATEGORY_CREW  default: Móda | Pánská móda | Pánské mikiny
    HEUREKA_CATEGORY_SET   default: Móda | Pánská móda | Pánská trička a tílka
    HEUREKA_CATEGORY_FALLBACK default: Móda | Pánská móda | Pánská trička a tílka
    HEUREKA_MANUFACTURER   default: Arche
    HEUREKA_VAT            default: 21%
    HEUREKA_DELIVERY_AVAILABLE   default: 0   (dní pokud skladem)
    HEUREKA_DELIVERY_UNAVAILABLE default: 7   (dní pokud out)
    HEUREKA_SHIPPING_ID    default: ZASILKOVNA
    HEUREKA_SHIPPING_PRICE default: 99
    HEUREKA_SHIPPING_PRICE_COD default: 129
    SKIP_UNAVAILABLE       default: 0  (1 = vyhodit out-of-stock varianty)
    OUTPUT_FILE            default: heureka.xml
"""
from __future__ import annotations

import html
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

SHOP = os.environ.get("SHOPIFY_SHOP", "archefashion.com").strip("/")
PUBLIC_DOMAIN = os.environ.get("SHOPIFY_PUBLIC_DOMAIN", f"https://{SHOP}").rstrip("/")

CATEGORY_FALLBACK = os.environ.get(
    "HEUREKA_CATEGORY_FALLBACK",
    "Móda | Pánská móda | Pánská trička a tílka",
)
CATEGORY_TEE = os.environ.get("HEUREKA_CATEGORY_TEE", CATEGORY_FALLBACK)
CATEGORY_CREW = os.environ.get(
    "HEUREKA_CATEGORY_CREW",
    "Móda | Pánská móda | Pánské mikiny",
)
CATEGORY_SET = os.environ.get("HEUREKA_CATEGORY_SET", CATEGORY_FALLBACK)

MANUFACTURER = os.environ.get("HEUREKA_MANUFACTURER", "Arche")
VAT = os.environ.get("HEUREKA_VAT", "21%")
DELIVERY_AVAILABLE = os.environ.get("HEUREKA_DELIVERY_AVAILABLE", "0")
DELIVERY_UNAVAILABLE = os.environ.get("HEUREKA_DELIVERY_UNAVAILABLE", "7")
SHIPPING_ID = os.environ.get("HEUREKA_SHIPPING_ID", "ZASILKOVNA")
SHIPPING_PRICE = os.environ.get("HEUREKA_SHIPPING_PRICE", "99")
SHIPPING_PRICE_COD = os.environ.get("HEUREKA_SHIPPING_PRICE_COD", "129")
SKIP_UNAVAILABLE = os.environ.get("SKIP_UNAVAILABLE", "0") == "1"
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "heureka.xml")

HEUREKA_PREFIX = "Heureka.cz | "


def fetch_products() -> list[dict[str, Any]]:
    """Stáhne všechny aktivní produkty z public Shopify /products.json (stránkováno ?page=N)."""
    import json

    products: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{PUBLIC_DOMAIN}/products.json?limit=250&page={page}"
        print(f"GET {url}", file=sys.stderr)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} on page {page}", file=sys.stderr)
            break
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(batch)
        if len(batch) < 250:
            break
        page += 1
    print(f"Fetched {len(products)} products", file=sys.stderr)
    return products


def determine_category(product: dict[str, Any]) -> str:
    """Rozumný category mapping podle product_type / handle / title."""
    haystack = " ".join(
        [
            (product.get("product_type") or "").lower(),
            (product.get("handle") or "").lower(),
            (product.get("title") or "").lower(),
        ]
    )
    if any(k in haystack for k in ("set", "everyday-set", "symbiosis")):
        return HEUREKA_PREFIX + CATEGORY_SET
    if any(k in haystack for k in ("crewneck", "mikina", "hoodie", "sweatshirt")):
        return HEUREKA_PREFIX + CATEGORY_CREW
    if any(k in haystack for k in ("tee", "t-shirt", "tricko", "tričko", "shirt")):
        return HEUREKA_PREFIX + CATEGORY_TEE
    return HEUREKA_PREFIX + CATEGORY_FALLBACK


def variant_image(product: dict[str, Any], variant: dict[str, Any]) -> str | None:
    """Najdi obrázek pro variantu (variant.image_id → product.images), fallback hlavní."""
    if vid := (variant.get("featured_image") or {}).get("src"):
        return vid
    if variant.get("image_id"):
        for img in product.get("images", []):
            if img.get("id") == variant["image_id"]:
                return img.get("src")
    images = product.get("images", [])
    if images:
        return images[0].get("src")
    return None


def alt_images(product: dict[str, Any], main: str | None, limit: int = 5) -> list[str]:
    out: list[str] = []
    for img in product.get("images", []):
        src = img.get("src")
        if not src or src == main:
            continue
        out.append(src)
        if len(out) >= limit:
            break
    return out


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def variant_sku(product: dict[str, Any], variant: dict[str, Any]) -> str:
    sku = variant.get("sku") or ""
    if sku.strip():
        return sku.strip()
    return f"ARCHE-{product.get('id')}-{variant.get('id')}"


def variant_param_names(product: dict[str, Any]) -> list[str]:
    """Čistá PARAM_NAME — pouze Shopify option names, bez product title prefixu."""
    names: list[str] = []
    for opt in product.get("options", []) or []:
        if isinstance(opt, dict):
            n = opt.get("name") or ""
        else:
            n = str(opt)
        n = n.strip()
        if not n or n.lower() == "title":
            continue
        names.append(n)
    return names


def variant_param_values(variant: dict[str, Any], n_params: int) -> list[str]:
    """Z option1/option2/option3 nebo z title rozdělit. Vrátí n_params hodnot."""
    vals: list[str] = []
    for i in range(1, 4):
        v = variant.get(f"option{i}")
        if v:
            vals.append(str(v).strip())
    if not vals:
        title = variant.get("title") or ""
        if title and title != "Default Title":
            vals = [p.strip() for p in title.split("/")]
    return vals[:n_params]


def el(tag: str, content: str | None, cdata: bool = False) -> str:
    if content is None or content == "":
        return ""
    if cdata:
        # CDATA — uvnitř smí být téměř cokoliv, ale `]]>` musíme rozdělit
        safe = str(content).replace("]]>", "]]]]><![CDATA[>")
        return f"  <{tag}><![CDATA[ {safe} ]]></{tag}>\n"
    safe = html.escape(str(content), quote=False)
    return f"  <{tag}>{safe}</{tag}>\n"


def build_shopitem(product: dict[str, Any], variant: dict[str, Any]) -> str:
    available = variant.get("available", True)
    if SKIP_UNAVAILABLE and not available:
        return ""
    price = variant.get("price") or "0"
    try:
        if float(price) <= 0:
            return ""
    except (TypeError, ValueError):
        return ""

    item_id = variant_sku(product, variant)
    title = product.get("title") or ""

    param_names = variant_param_names(product)
    param_vals = variant_param_values(variant, len(param_names))

    suffix = ""
    if param_vals:
        suffix = " (" + ", ".join(param_vals) + ")"

    product_name = (title + suffix).strip()
    main_img = variant_image(product, variant)
    alts = alt_images(product, main_img)
    handle = product.get("handle") or ""
    url = f"{PUBLIC_DOMAIN}/products/{handle}"
    description = strip_html(product.get("body_html"))[:2000]
    category = determine_category(product)
    vendor = product.get("vendor") or MANUFACTURER
    delivery_date = DELIVERY_AVAILABLE if available else DELIVERY_UNAVAILABLE
    itemgroup_id = str(product.get("id") or "")

    parts: list[str] = []
    parts.append("<SHOPITEM>\n")
    parts.append(el("ITEM_ID", item_id))
    parts.append(el("PRODUCTNAME", product_name, cdata=True))
    parts.append(el("PRODUCT", title, cdata=True))
    if description:
        parts.append(el("DESCRIPTION", description, cdata=True))
    parts.append(el("URL", url))
    if main_img:
        parts.append(el("IMGURL", main_img))
    for a in alts:
        parts.append(el("IMGURL_ALTERNATIVE", a))
    parts.append(el("PRICE_VAT", f"{float(price):.2f}"))
    parts.append(el("VAT", VAT))
    parts.append(el("CATEGORYTEXT", category))
    parts.append(el("MANUFACTURER", vendor))
    for name, val in zip(param_names, param_vals):
        parts.append("  <PARAM>\n")
        parts.append("  " + el("PARAM_NAME", name).strip() + "\n")
        parts.append("  " + el("VAL", val).strip() + "\n")
        parts.append("  </PARAM>\n")
    parts.append(el("DELIVERY_DATE", delivery_date))
    parts.append("  <DELIVERY>\n")
    parts.append("  " + el("DELIVERY_ID", SHIPPING_ID).strip() + "\n")
    parts.append("  " + el("DELIVERY_PRICE", SHIPPING_PRICE).strip() + "\n")
    parts.append("  " + el("DELIVERY_PRICE_COD", SHIPPING_PRICE_COD).strip() + "\n")
    parts.append("  </DELIVERY>\n")
    parts.append(el("ITEM_TYPE", "new"))
    parts.append(el("ITEMGROUP_ID", itemgroup_id))
    parts.append("</SHOPITEM>\n")
    return "".join(parts)


def main() -> None:
    products = fetch_products()
    items_xml: list[str] = []
    items_count = 0
    skipped = 0

    for product in products:
        for variant in product.get("variants", []) or []:
            block = build_shopitem(product, variant)
            if block:
                items_xml.append(block)
                items_count += 1
            else:
                skipped += 1

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    head = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<!-- ARCHE Heureka feed, currency=CZK, generated {generated_at} "
        f"({items_count} items, {skipped} skipped) -->\n"
        "<SHOP>\n"
    )
    tail = "</SHOP>\n"

    xml = head + "".join(items_xml) + tail

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(xml)

    print(f"OK: {items_count} SHOPITEM in {OUTPUT_FILE} ({len(xml)} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
