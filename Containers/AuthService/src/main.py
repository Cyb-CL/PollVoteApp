
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware
import os
import datetime
import jwt
import bcrypt

#MongoDB connection
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["polldb"]
users_collection = db["users"]

# Configurazione JWT (segreto condiviso tra i microservizi)
JWT_SECRET = os.environ.get("JWT_SECRET", "secretkey-pollvoteapp")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

app = FastAPI(title="Auth Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserAuth(BaseModel):
    username: str
    password: str

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(username: str) -> str:
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": username,
        "exp": expiration
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ENDPOINT: Registration of the new user
@app.post("/register")
def register_user(user: UserAuth):
    username = user.username.strip()
    password = user.password.strip()

    # Validazione campi non vuoti e lunghezza minima
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password cannot be empty")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long")

    existing_user = users_collection.find_one({"username": username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = hash_password(password)
    users_collection.insert_one({
        "username": username,
        "password_hash": hashed_pw
    })

    token = create_access_token(username)
    return {
        "message": "User registered successfully",
        "username": username,
        "access_token": token,
        "token_type": "bearer"
    }

# ENDPOINT: Login 
@app.post("/login")
def login_user(user: UserAuth):
    username = user.username.strip()
    db_user = users_collection.find_one({"username": username})

    # Controllo credenziali (utente esistente e password corretta)
    if not db_user or not verify_password(user.password, db_user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Generazione e restituzione del token JWT
    token = create_access_token(username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }

# ENDPOINT: Verify the current user
@app.get("/me")
def get_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}
