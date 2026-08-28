import uvicorn
from nivasha.api.main import app

if __name__ == "__main__":
    uvicorn.run("nivasha.api.main:app", host="127.0.0.1", port=8000, reload=True)
