# mimiru# main.py

# 必要なライブラリをインポートします
# FastAPI: APIサーバーを簡単に作るためのフレームワーク
# Pydantic: データの型を定義・検証するためのライブラリ
# Passlib: パスワードを安全に扱うためのライブラリ
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from typing import List

# FastAPIアプリケーションを初期化します
app = FastAPI()

# パスワードをハッシュ化（暗号化）するための設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- データベースの代わり (シミュレーション用) ---
# 本来はSupabaseなどのデータベースに保存しますが、
# まずはプログラムが動いている間だけユーザー情報を記憶するリストを使います。
fake_users_db = []
# -----------------------------------------

# --- データモデルの定義 (Pydanticを使用) ---

# ユーザー登録時に受け取るデータ形式を定義
class UserCreate(BaseModel):
    company_name: str
    email: EmailStr
    password: str

# ユーザー情報を返す時のデータ形式を定義 (パスワードは含めない)
class UserOut(BaseModel):
    id: int
    company_name: str
    email: EmailStr

# ログイン時に受け取るデータ形式を定義
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# トークンを返す時のデータ形式を定義
class Token(BaseModel):
    access_token: str
    token_type: str

# --- パスワード関連の関数 ---

# パスワードをハッシュ化する関数
def get_password_hash(password):
    return pwd_context.hash(password)

# 入力されたパスワードがハッシュ化されたパスワードと一致するか検証する関数
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- APIエンドポイントの作成 ---

# 1. 新規ユーザー登録API
@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    # 同じメールアドレスのユーザーが既に存在するかチェック
    for db_user in fake_users_db:
        if db_user["email"] == user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="このメールアドレスは既に使用されています。"
            )
    
    # パスワードをハッシュ化
    hashed_password = get_password_hash(user.password)
    
    # 新しいユーザーデータを作成
    new_user = {
        "id": len(fake_users_db) + 1,
        "company_name": user.company_name,
        "email": user.email,
        "hashed_password": hashed_password
    }
    
    # データベースの代わりにリストに追加
    fake_users_db.append(new_user)
    
    # パスワードを除いたユーザー情報を返す
    return {
        "id": new_user["id"],
        "company_name": new_user["company_name"],
        "email": new_user["email"]
    }

# 2. ログインAPI
@app.post("/login", response_model=Token)
def login_for_access_token(form_data: UserLogin):
    user = None
    # メールアドレスでユーザーを検索
    for db_user in fake_users_db:
        if db_user["email"] == form_data.email:
            user = db_user
            break
            
    # ユーザーが存在しない、またはパスワードが間違っている場合
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ログイン成功後、アクセストークンを生成（ここでは簡単なダミー文字列）
    # 実際のサービスではJWT (JSON Web Token) という技術を使います
    access_token = f"dummy_token_for_{user['email']}"
    
    return {"access_token": access_token, "token_type": "bearer"}

# 3. 登録ユーザー一覧を取得するAPI (動作確認用)
@app.get("/users", response_model=List[UserOut])
def read_users():
    # パスワードを除いたユーザー情報のみを返す
    return [
        {"id": u["id"], "company_name": u["company_name"], "email": u["email"]} 
        for u in fake_users_db
    ]

# ルートURLへのアクセス（サーバーが起動しているか確認用）
@app.get("/")
def read_root():
    return {"message": "ミミル バックエンドAPIへようこそ！"}

