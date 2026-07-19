/** Beginner-friendly help copy for each dashboard section. */

export const GLOSSARY = [
  {
    term: "Long",
    meaning:
      "You buy a stock hoping the price goes up. You profit if it rises; you lose if it falls.",
  },
  {
    term: "Short",
    meaning:
      "You bet that a stock will fall. You profit if the price drops; you lose if it rises. Shorting has extra rules and risks.",
  },
  {
    term: "Entry",
    meaning: "The price where the bot would start the trade.",
  },
  {
    term: "Target (take-profit)",
    meaning:
      "The price where you lock in a win. Example: target 1% means you aim to make about 1% before exiting.",
  },
  {
    term: "Stop (stop-loss)",
    meaning:
      "The price where you cut a losing trade to limit damage. Example: stop 0.5% means you accept roughly a 0.5% loss if the trade goes wrong.",
  },
  {
    term: "Stake",
    meaning: "How much money (in dollars) you would put into that one trade.",
  },
  {
    term: "P(success)",
    meaning:
      "The bot’s estimated chance (0 to 1, or 0% to 100%) that price hits the target before the stop, based on past similar situations. It is a guide, not a guarantee.",
  },
  {
    term: "Edge",
    meaning:
      "Whether the trade looks worthwhile after weighing win chance against target and stop sizes. Positive edge means the maths looks favourable; negative means skip it.",
  },
  {
    term: "Advisory mode",
    meaning:
      "The bot only suggests ideas. It does not place real or paper orders until you change the mode in settings.",
  },
];

export const GUIDE = {
  title: "How to use this app",
  intro:
    "This dashboard shows what the trading bot is thinking in plain language. It watches US stocks, estimates how likely a trade is to hit your profit target before your stop-loss, then labels each idea APPROVED, WATCHLIST, or REJECTED. You do not need to be an expert to follow along — start here, then open each page’s Help button for details.",
  steps: [
    {
      title: "1. Check Live",
      body: "Open Live to see decisions as they appear. Green APPROVED means the bot thinks the setup is strong enough. Amber WATCHLIST means “interesting, but not ready.” Red REJECTED means skip for now.",
    },
    {
      title: "2. Understand one row",
      body: "Pick any decision and read: Symbol (which stock), Side (long = up, short = down), P(success) (chance of hitting target first), Entry / Target / Stop (the plan prices), and Reasons (why the bot chose that label).",
    },
    {
      title: "3. Browse the other pages",
      body: "Scanner shows which stocks are being watched. Watchlist is for ideas you want to keep an eye on. Positions shows trades already open. History is the past record. Model shows how reliable the probability estimates have been. Risk & Controls lets you set limits and an emergency stop.",
    },
    {
      title: "4. Stay safe",
      body: "Default mode is advisory — suggestions only. Paper mode practises with fake money. Live mode uses real money and should only be turned on when you fully understand the risks. Use the Kill switch on Risk & Controls if you need everything to stop placing new trades immediately.",
    },
  ],
  important:
    "Past patterns do not guarantee future results. Free market data is incomplete compared with professional feeds. Treat APPROVED as “worth a closer look,” not “guaranteed profit.”",
};

export const SECTION_HELP = {
  live: {
    title: "Live",
    summary: "Real-time feed of trade ideas the bot just evaluated.",
    paragraphs: [
      "This is the main scoreboard. Every few seconds the bot scans stocks, builds a plan (entry, target, stop), estimates the chance of success, and shows a decision.",
      "You do not place trades from this page yourself. In advisory mode the bot only records ideas. In paper or live mode, APPROVED ideas may become orders automatically.",
    ],
    bullets: [
      {
        label: "APPROVED (green)",
        text: "Risk checks passed and the expected edge looks good enough. Strongest ideas.",
      },
      {
        label: "WATCHLIST (amber)",
        text: "Somewhat promising, but not strong enough yet — or the entry is not ready. Keep watching.",
      },
      {
        label: "REJECTED (red)",
        text: "Skipped: bad risk, weak probability, or negative edge. Normal — most ideas are rejected.",
      },
      {
        label: "P(success)",
        text: "Estimated probability the price hits the target before the stop. 0.60 means about 60%.",
      },
      {
        label: "Edge",
        text: "Combines win chance with how big the win vs loss would be. Positive = maths looks OK; negative = skip.",
      },
      {
        label: "● / ○",
        text: "Filled circle means the live connection is working. Empty means it is disconnected — refresh the page.",
      },
      {
        label: "KILL badge",
        text: "Emergency stop is on. No new trades will be sent. Clear it under Risk & Controls when safe.",
      },
    ],
  },
  watchlist: {
    title: "Watchlist",
    summary: "Stocks you (or the bot) want to keep an eye on.",
    paragraphs: [
      "Two kinds of watchlist live here. Manual symbols are tickers you type in yourself (for example AAPL). Decision cards with status WATCHLIST are ideas the bot flagged as “maybe later.”",
      "Adding a symbol does not buy anything — it only tells the scanner to pay more attention to that stock.",
    ],
    bullets: [
      {
        label: "Add symbol",
        text: "Type a US ticker (like MSFT) and click Add. Click a chip with × to remove it.",
      },
      {
        label: "WATCHLIST cards",
        text: "Bot ideas that were not APPROVED yet. Check P(success), edge, and reasons to see what is missing.",
      },
    ],
  },
  positions: {
    title: "Positions",
    summary: "Trades you already hold (paper or live).",
    paragraphs: [
      "A position means money is already in a trade. Long means you own shares; short means you are betting the price falls.",
      "In advisory mode this list is often empty because the bot is not placing orders. The chart is a simple price view to help you picture where a position sits.",
    ],
    bullets: [
      {
        label: "Qty",
        text: "How many shares. A negative number usually means a short position.",
      },
      {
        label: "Avg entry",
        text: "Average price you got into the trade at.",
      },
      {
        label: "uPnL (unrealized profit/loss)",
        text: "Paper gain or loss if you closed right now. It changes as the price moves.",
      },
    ],
  },
  scanner: {
    title: "Scanner",
    summary: "Which stocks the bot is looking at right now.",
    paragraphs: [
      "The scanner ranks stocks by liquidity (how easy they are to trade) and other filters like news activity. Higher-ranked names get more attention.",
      "Free data limits how many stocks can be watched on the live tape at once (about 30). Those appear under WebSocket slots.",
    ],
    bullets: [
      {
        label: "Liq score",
        text: "Higher usually means more trading activity — easier to enter and exit without wild gaps.",
      },
      {
        label: "News",
        text: "Rough “something is in the headlines” heat. It is not full sentiment analysis.",
      },
      {
        label: "ETB / Shortable",
        text: "Easy to borrow — needed before the bot will seriously consider a short trade.",
      },
      {
        label: "Why",
        text: "Short tags explaining why this name was included (watchlist, news heat, liquid, and so on).",
      },
    ],
  },
  history: {
    title: "History",
    summary: "Past decisions, fills, and daily profit/loss.",
    paragraphs: [
      "Use History to look back: what did the bot suggest yesterday? Did paper/live trades make or lose money?",
      "The Daily PnL chart shows profit and loss by day when that data exists. Filtering by status helps you study only APPROVED ideas, for example.",
    ],
    bullets: [
      {
        label: "Daily PnL",
        text: "Up days vs down days. Empty chart means no daily totals have been recorded yet.",
      },
      {
        label: "Status filter",
        text: "Narrow the decision list to APPROVED, WATCHLIST, or REJECTED.",
      },
      {
        label: "Edge $",
        text: "Rough dollar estimate of edge for that stake size — not the actual money made.",
      },
    ],
  },
  model: {
    title: "Model",
    summary: "How well the probability estimates are working.",
    paragraphs: [
      "The “model” is the maths that turns market patterns into a chance of success. This page is a report card for that maths.",
      "If Ready is No, run training (or wait for the nightly job). Until then the bot falls back to a simple baseline guess.",
    ],
    bullets: [
      {
        label: "Brier score",
        text: "Lower is better. It measures how accurate the probability forecasts were on test data.",
      },
      {
        label: "No-skill baseline",
        text: "The hit rate you’d expect from random chance given your target and stop sizes. The model should beat this.",
      },
      {
        label: "Beats baseline",
        text: "Yes means the model looked better than coin-flip geometry on the test set. Still not a promise of future profits.",
      },
      {
        label: "Calibration buckets",
        text: "When the bot said “about 40%,” how often did those trades actually win? Bars should line up roughly with the predicted chance.",
      },
    ],
  },
  risk: {
    title: "Risk & Controls",
    summary: "Safety limits and knobs that shape every trade plan.",
    paragraphs: [
      "This page is your seatbelt. Caps stop the bot from risking too much on one trade or in one day. The kill switch freezes new order activity.",
      "Mode (advisory / paper / live) is shown here but changed only in the server .env file on purpose — so a click in the browser cannot suddenly switch to real money.",
    ],
    bullets: [
      {
        label: "Kill switch",
        text: "Engage = stop new trades immediately. Clear = allow the pipeline to continue. Always journaled for your audit trail.",
      },
      {
        label: "target_pct",
        text: "Profit goal as a percent of price (e.g. 1.0 = aim for about +1%).",
      },
      {
        label: "stop_pct",
        text: "Max loss you accept as a percent (e.g. 0.5 = cut at about −0.5%).",
      },
      {
        label: "stake_quote",
        text: "Dollars to risk/allocate per idea when sizing the plan.",
      },
      {
        label: "horizon_minutes",
        text: "How long (in minutes) the bot waits for target or stop before giving up on that idea.",
      },
      {
        label: "p_min",
        text: "Minimum success probability required. Below this → REJECTED.",
      },
      {
        label: "edge_approve",
        text: "How strong the edge must be before APPROVED. Below it (but still OK) → WATCHLIST.",
      },
      {
        label: "Gross exposure",
        text: "Total dollars currently tied up across positions. Must stay under the cap.",
      },
    ],
  },
  logs: {
    title: "Logs",
    summary: "System diary: starts, errors, risk events, and monitor updates.",
    paragraphs: [
      "When something odd happens — a disconnect, a rejected order, a kill switch — it usually appears here first.",
      "You do not need to read Logs every day. Check it if Live looks stuck or decisions suddenly stop.",
    ],
    bullets: [
      {
        label: "Level",
        text: "INFO is normal. WARNING/ERROR deserve a closer look.",
      },
      {
        label: "Kind",
        text: "Category tags like stream, order, kill_switch, control, monitor.",
      },
    ],
  },
};
