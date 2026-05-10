# Maison Lumière — Beauty Salon Booking

One-page booking website for a beauty salon. Vanilla HTML/CSS/JS with Supabase for appointment storage.

## Local setup

```bash
# 1. Clone / open the project
cd beauty-salon-booking

# 2. Add your Supabase credentials
cp js/config/env.example.js js/config/env.js
# Edit js/config/env.js and fill in SUPABASE_URL and SUPABASE_ANON_KEY

# 3. Start a local server (ES modules require HTTP, not file://)
npx live-server --port=3000 --open=index.html
# or: npm run dev
```

> Without Supabase credentials the site runs in **demo mode** — form submissions are simulated and logged to the console.

## Supabase table schema

Run this SQL in your Supabase project (SQL Editor → New query):

```sql
CREATE TABLE appointments (
  id               uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at       timestamptz DEFAULT now(),
  name             text        NOT NULL,
  phone            text        NOT NULL,
  service          text        NOT NULL,
  appointment_date date        NOT NULL,
  appointment_time time        NOT NULL,
  notes            text,
  status           text        DEFAULT 'pending'
);

-- Optional: enable Row Level Security and allow inserts from anon
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public insert" ON appointments
  FOR INSERT TO anon WITH CHECK (true);
```

## Project structure

```
beauty-salon-booking/
├── index.html              # Single HTML shell
├── css/
│   ├── main.css            # Imports all partials
│   ├── base/               # Variables, reset, typography
│   ├── components/         # Buttons, cards, form, toasts
│   └── sections/           # Nav, hero, services, booking, about, footer
└── js/
    ├── main.js             # Entry point
    ├── config/
    │   ├── supabase.js     # Supabase client init
    │   ├── env.js          # Credentials (gitignored)
    │   └── env.example.js  # Template
    ├── modules/
    │   ├── booking.js      # Multi-step form logic
    │   ├── services.js     # Service catalog & selection
    │   ├── calendar.js     # Date picker & time slots
    │   └── notifications.js# Toast messages
    └── utils/
        ├── validation.js   # Input validators
        ├── formatters.js   # Date/price formatters
        └── domHelpers.js   # $ / $$ / setBtn helpers
```

## Deployment (Vercel)

1. Push the `beauty-salon-booking/` folder to a GitHub repo
2. Import the repo in [vercel.com](https://vercel.com) — no build settings needed (static site)
3. Add environment variables in Vercel dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
4. Since this is a vanilla JS project without a build step, copy the env values directly into `js/config/env.js` **before deploying**, or use a CI step to inject them.

## Customising

| What | Where |
|---|---|
| Services list | `js/modules/services.js` → `SERVICES` array |
| Color palette | `css/base/_variables.css` → `:root` |
| Working days / closed days | `js/modules/calendar.js` → `CLOSED_DAYS` |
| Time slots | `js/modules/calendar.js` → `ALL_SLOTS` |
| Salon name, address, phone | `index.html` footer section |
