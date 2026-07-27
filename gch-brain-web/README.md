# GCH Company Brain - Web Interface

A tiny web app to ask your brain from a browser. It reads from the same Supabase
you filled with `ingest.py`. Deploys to Vercel.

```
Browser  ->  /api/ask (Vercel server)  ->  Supabase (find chunks) + OpenAI (write answer)
```

Your secret Supabase key lives only in the Vercel function, never in the browser.

## What's here
- `index.html`      - the chat page (what people see)
- `api/ask.js`      - the server function that does the RAG
- `package.json`    - the two libraries the function needs

## Deploy to Vercel (about 10 minutes)

### 1. Install the tools (one time)
Make sure you have Node installed. In Terminal:
```
node -v
```
If that prints a version, you're good. If "command not found", install Node from
https://nodejs.org (LTS version), then reopen Terminal.

Install the Vercel command-line tool:
```
npm install -g vercel
```

### 2. Deploy
In Terminal, go to this folder and run vercel:
```
cd "/Users/varadutt/Desktop/henge work/gch-brain-web"
vercel
```
Follow the prompts (log in with your email/GitHub, accept the defaults, "yes" to
deploy). It gives you a live URL when done.

### 3. Add your keys (so the function can reach Supabase + OpenAI)
The function needs three secrets. Add them:
```
vercel env add OPENAI_API_KEY
vercel env add SUPABASE_URL
vercel env add SUPABASE_SERVICE_KEY
```
Paste each value when asked, and choose "Production" (and Preview/Development if
offered). These are the SAME values from your ingest project's .env file.

You can also add them in the dashboard: vercel.com -> your project -> Settings ->
Environment Variables.

### 4. Redeploy so the keys take effect
```
vercel --prod
```
Open the URL it prints. Type a question. Done.

## Test locally first (optional)
```
vercel dev
```
This runs it at http://localhost:3000 using your keys. Handy before deploying.

## Notes
- This app only ASKS the brain. Filling it stays the job of `ingest.py`, which you
  run on your computer.
- Cost per question is about 1-2 cents (one OpenAI answer). Set a spending limit on
  OpenAI for peace of mind.
- To change the look, edit `index.html`. To change how it answers, edit the prompt
  in `api/ask.js`.
