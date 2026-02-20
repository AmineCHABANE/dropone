from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
async def health():
    errors = []
    try:
        import stripe
    except Exception as e:
        errors.append(f"stripe: {e}")
    try:
        from openai import OpenAI
    except Exception as e:
        errors.append(f"openai: {e}")
    try:
        import httpx
    except Exception as e:
        errors.append(f"httpx: {e}")
    try:
        import database
    except Exception as e:
        errors.append(f"database: {e}")
    try:
        import catalog
    except Exception as e:
        errors.append(f"catalog: {e}")
    try:
        import store_generator
    except Exception as e:
        errors.append(f"store_generator: {e}")
    try:
        import content_ai
    except Exception as e:
        errors.append(f"content_ai: {e}")
    try:
        import multi_store
    except Exception as e:
        errors.append(f"multi_store: {e}")
    try:
        import notifications
    except Exception as e:
        errors.append(f"notifications: {e}")
    try:
        import cj_client
    except Exception as e:
        errors.append(f"cj_client: {e}")
    return {"status": "ok" if not errors else "errors", "errors": errors}
