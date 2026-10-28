# Deep Regrats: the website

The public site for **Deep Regrats**, the iPhone game by Flipware (bundle id `se.flipware.spelet`): the start page,
the privacy policy in English and Swedish, and `app-ads.txt` for Google AdMob. Plain HTML, CSS and JavaScript with no
build step, published with GitHub Pages from `main`, folder `/` (root).

Live: <https://ftronnbe.github.io/spelet-public/>

| Page | URL |
|---|---|
| Start page | https://ftronnbe.github.io/spelet-public/ |
| Privacy policy (English) | https://ftronnbe.github.io/spelet-public/privacy.html |
| Integritetspolicy (svenska) | https://ftronnbe.github.io/spelet-public/integritetspolicy.html |
| app-ads.txt | https://ftronnbe.github.io/spelet-public/app-ads.txt |

## Files

- `index.html`: the start page (hero with the archway, features, monsters, classes, Kevin, screenshots, FAQ).
- `privacy.html`, `integritetspolicy.html`: the privacy policy. Keep the two in step; both carry the effective date.
- `404.html`: self-contained, so it works from any path.
- `app-ads.txt`: the AdMob seller line (see the caveat below).
- `assets/css/style.css`, `assets/js/main.js`: all styling and motion. Everything respects `prefers-reduced-motion`.
- `assets/js/links.js`: **the store links** (see below).
- `assets/fonts/`: self-hosted WOFF2 fonts (Cinzel Decorative, Pirata One, Alegreya Sans; SIL Open Font License, the
  licence texts are next to them). The site makes no requests to any other host: no Google Fonts, no CDN, no analytics,
  no cookies.
- `assets/sprites/`: walk cycles cut from the game's own sprite sheets (one facing, frames side by side, animated with
  CSS `steps()`), the three heroes composited from the hero layer sheets, Kevin and his six hats.
- `assets/shots/`: real screenshots from a simulator build (800 and 1400 px wide WebP).
- `assets/img/`: icons from the app icon, the class emblems, a couple of props, the social preview `og-image.jpg`.

All art is the game's own (from the `spelet` repository). Nothing third-party.

## Adding the TestFlight and App Store links

Edit **one file**, `assets/js/links.js`:

```js
window.DEEP_REGRATS_LINKS = {
  testFlight: "https://testflight.apple.com/join/XXXXXXXX",
  appStore: "https://apps.apple.com/app/idNNNNNNNNNN",
};
```

An empty string keeps that button as a "coming soon" placeholder that goes nowhere. Commit and push; Pages updates in a
minute or two.

## Changing the privacy policy

Edit both `privacy.html` and `integritetspolicy.html`, change the date at the top ("Effective from" / "Gäller från"),
and keep the URLs stable: they are entered in App Store Connect and in AdMob. If the game starts collecting something
new (usage statistics with PostHog, crash reports), update the policy **before** that version ships.

## app-ads.txt and the domain (important)

AdMob (and other ad crawlers) look for `app-ads.txt` **at the root of the developer website's domain**, the domain of
the URL on the App Store listing. This site is a GitHub Pages *project* site, so its file is at
`https://ftronnbe.github.io/spelet-public/app-ads.txt`, not at `https://ftronnbe.github.io/app-ads.txt`. A crawler that
looks at the root of `ftronnbe.github.io` will not find it. Two ways to fix that:

1. **A custom domain for this site (recommended).** For example `deepregrats.com`, or a subdomain of a domain you own
   such as `deepregrats.flipware.se`.
   - DNS: for a subdomain, a `CNAME` record pointing at `ftronnbe.github.io`; for an apex domain, the four GitHub Pages
     `A` records (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and the matching `AAAA` records.
   - Add a file `CNAME` at the root of this repository containing just the domain, e.g. `deepregrats.com`
     (or set it under Settings > Pages > Custom domain, which commits the same file), then tick "Enforce HTTPS".
   - The site then lives at the root of that domain, so `https://deepregrats.com/app-ads.txt` works as AdMob expects.
   - In App Store Connect use `https://deepregrats.com/` as the Marketing URL (and Support URL), and
     `https://deepregrats.com/privacy.html` as the Privacy Policy URL. Update the canonical and `og:` URLs in the HTML.
2. **A user site repository `ftronnbe/ftronnbe.github.io`.** Its root is served at `https://ftronnbe.github.io/`, so an
   `app-ads.txt` there is at the domain root. Then the developer website on the App Store listing can be
   `https://ftronnbe.github.io/` (or this site's URL, which is on the same host). Note that this repository's own copy
   stays useful as a mirror, but the one AdMob reads would be the one in `ftronnbe.github.io`. This works, but every
   app you ever publish would share that one domain and one `app-ads.txt`.

Until one of these is done, keep the URLs above in App Store Connect anyway; the privacy policy links work today, and
AdMob shows ads before app-ads.txt is verified (just possibly fewer of them).

## Regenerating assets

The sprite strips, icons and the social image were made with small Pillow scripts from the game repository's art
(`Spelet/Sprites/*_Walking_A.png`: 8 direction columns S, SW, W, NW, N, NE, E, SE, one row per frame; the SE column is
used; `Spelet/Hero/hero_<layer>_<clip>.png` composited in `HeroLook.swift`'s order with its skin and hair tints;
`cat_sheet.png` + `cat_hats.png` placed with `CatSheet.headTop`, `CatHatSheet` and `CatBalance.hatDrop`). The
screenshots come from a Debug simulator build launched with the game's debug flags (for example
`-newGame -class barbarian -level 20 -seedLoot -townLevel 3 -noDeals -noCatPrompt -cat -noAds`), with the Dynamic
Island strip cropped off.

## Local preview

```sh
python3 -m http.server 8000
# open http://localhost:8000/
```
