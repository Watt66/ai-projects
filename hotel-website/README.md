# Whitesands Beach Resort & Spa — Demo Hotel Website

A responsive, single-page hotel website inspired by the layout of the Sarova Whitesands (Mombasa) site. Built as a self-contained static site — one `index.html` with embedded CSS and JS. No build step or dependencies.

## Structure (mirrors the source site)
- Sticky top bar + navigation with "Book Now" CTA
- Full-height hero with booking widget (hotel / arrival / departure / adults / children)
- About section with key stats (340 rooms, 5 pools, 1,200 event capacity)
- Rooms & Suites cards (Ocean View, Garden Suites, Presidential)
- Restaurants & Bars (Thai Chi By The Sea, Lido Lounge, Coco's Beach Bar)
- Tulia Spa split feature
- Conferences, Weddings & Ozone Kids Club
- Rewards band
- Guest testimonials grid
- Things to Do in Mombasa (Fort Jesus, Haller Park, watersports)
- FAQ accordion
- Footer with contact details

## Run it
Just open `index.html` in any browser, or serve locally:
```bash
cd hotel-website
python3 -m http.server 8000
# visit http://localhost:8000
```

## Notes
- Imagery uses Unsplash placeholder photos (free, royalty-free).
- Text is original copy written in the same tone/structure as the source — not a verbatim copy of Sarova's trademarked content.
- The booking widget is a front-end demo (shows an alert). Wire it to a real reservation API to go live.
