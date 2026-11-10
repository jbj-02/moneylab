# Optional cloud AI setup

**You do not need a key for Smart paste or guided setup.** Only the optional third-party **cloud AI** path is disabled by default; it remains available for a later experiment if the owner wishes to configure a provider. To enable the existing OpenAI connector, the owner must configure the following in their Streamlit Community Cloud app's **Settings → Secrets** area (do **not** commit real values to GitHub):

```toml
OPENAI_API_KEY = "YOUR_PRIVATE_OPENAI_API_KEY"
MONEYLAB_ENABLE_AI_SETUP = true
```

The server makes bounded calls to the OpenAI Responses API using a supported compact model (currently `gpt-4.1-mini`). The code requests structured output and sets `store = false`, and does not save the original description in the MoneyLab profile. Users must check a consent box before any external request. It is **not automatically included with a ChatGPT subscription**; the account owner must arrange separate API access and billing. See [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [Streamlit Cloud secrets](https://docs.streamlit.io/deploy/concepts/secrets).

**Public-deployment caution:** A three-request limit per browser session, a description length limit and bounded output help reduce accidental usage, but are **not** secure per-user rate limiting. Before enabling AI for an unrestricted public audience, add real authentication / per-user quotas, spending limits, abuse monitoring and a privacy review. Financial descriptions submitted to AI are transmitted to an external service and subject to that service's data policies. Do not solicit banking credentials, account numbers or personally identifying information.
