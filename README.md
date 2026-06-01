# ARCHE Heureka feed

Automaticky generovaný Heureka.cz XML feed z [archefashion.com](https://archefashion.com).

## Live feed URL

```
https://raw.githubusercontent.com/u7279101060-ux/heureka-feed/main/heureka.xml
```

Tuhle URL vlož do **sluzby.heureka.cz → Správce zboží → XML feed**.

## Jak to funguje

- `generate_heureka_xml.py` stahuje produkty z public Shopify endpointu
  `https://archefashion.com/products.json` (žádný token, žádná auth).
- Generuje Heureka 2026 spec kompatibilní XML:
  - `DELIVERY` element (Zásilkovna, 99 / 129 COD Kč)
  - `CATEGORYTEXT` s `Heureka.cz |` prefixem
  - Smart category mapping (trička / mikiny / sety)
  - `ITEMGROUP_ID` (varianty jednoho produktu sdílejí ID)
  - `DELIVERY_DATE` per `variant.available` (0 dní skladem / 7 dní mimo)
- GitHub Actions cron běží **každé 4 hodiny**, commitne `heureka.xml` jen pokud
  se obsah změnil.
- Manuální trigger: **Actions → Update Heureka feed → Run workflow**.

## Lokální spuštění

```bash
python generate_heureka_xml.py
# heureka.xml ve working dir
```

## Konfigurace

Default values sedí pro ARCHE. Override přes GitHub repo **Settings → Secrets
and variables → Actions → Variables**:

| Var | Default | Pozn. |
|---|---|---|
| `SHOPIFY_SHOP` | `archefashion.com` | Custom doména, NE `myshopify.com` |
| `HEUREKA_CATEGORY_TEE` | `Móda \| Pánská móda \| Pánská trička a tílka` | Pro tee/t-shirt |
| `HEUREKA_CATEGORY_CREW` | `Móda \| Pánská móda \| Pánské mikiny` | Pro crewneck/mikina |
| `HEUREKA_CATEGORY_SET` | (= `_FALLBACK`) | Pro sety |
| `HEUREKA_CATEGORY_FALLBACK` | `Móda \| Pánská móda \| Pánská trička a tílka` | Když nic nesedí |
| `HEUREKA_MANUFACTURER` | `Arche` | Override pokud Shopify vendor je nevhodný |
| `HEUREKA_VAT` | `21%` | |
| `HEUREKA_SHIPPING_ID` | `ZASILKOVNA` | |
| `HEUREKA_SHIPPING_PRICE` | `99` | Kč, bez COD |
| `HEUREKA_SHIPPING_PRICE_COD` | `129` | Kč, s dobírkou |
| `HEUREKA_DELIVERY_AVAILABLE` | `0` | Dní, skladem |
| `HEUREKA_DELIVERY_UNAVAILABLE` | `7` | Dní, mimo |

Prefix `Heureka.cz |` se přidává automaticky.

## Heureka spec

- Specifikace polí: https://heureka.github.io/xml-feed-specs/
- Strom kategorií: https://www.heureka.cz/direct/xml-export/shops/heureka-sekce.xml

## Troubleshooting

| Problém | Fix |
|---|---|
| Actions: 0 items | `archefashion.com/products.json` vrátil prázdno → mrkni že Shopify má active produkty |
| Heureka: „neznámá kategorie" | `HEUREKA_CATEGORY_*` musí přesně sedět na Heureka strom |
| Heureka: „chybí DELIVERY" | Workflow může selhat během generování → mrkni Actions log |
| Stale feed | Actions může být disabled (Settings → Actions → General → „Allow all"); manuál Run workflow |

## Co tenhle generátor NEdělá (záměrně)

- **EAN** — ARCHE zatím nemá. Až bude, doplnit z Shopify metafieldu.
- **`HEUREKA_CPC`** — bidding tier nepoužíváme.
- **Více DELIVERY možností** — jediná Zásilkovna. Pokud přibyde PPL / ČP, rozšíř `<DELIVERY>` element ve scriptu.
- **Per-collection category** — všechny tee/crew jdou stejnou cestou. Až bude potřeba (např. dámská sekce), rozšířit `determine_category()` o `collection_handle` mapování.

## Související

- Plán a historie ve Vaultu: `Návody/Shopify-Heureka-XML-feed.md`,
  `Rozhodnutí/Heureka-feed-github-actions.md`,
  `Rozhodnutí/Heureka-2026-DELIVERY-element.md`
- AIOS TODO: `todos/heureka-feed-fix.md` (private)
