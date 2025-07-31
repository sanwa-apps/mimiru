# main.py

# --- 必要なライブラリをインポート ---
import os
import io
from fastapi import FastAPI, HTTPException, status, File, UploadFile, Form
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from typing import List

# RAG機能のために追加するライブラリ
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.chains import ConversationalRetrievalChain

# --- 初期設定 ---

# FastAPIアプリケーションを初期化
app = FastAPI()

# Google AI Studioで取得したAPIキーを設定
# 実際の運用では環境変数として設定するのが安全です
os.environ["GOOGLE_API_KEY"] = "YOUR_GOOGLE_API_KEY_HERE"

# パスワードをハッシュ化（暗号化）するための設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- データベースの代わり (シミュレーション用) ---
fake_users_db = []
# 各ユーザーのベクトルストア（AIの知識ベース）を保存する場所
vector_stores = {}
# -----------------------------------------

# --- データモデルの定義 ---
class UserCreate(BaseModel):
    company_name: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    company_name: str
    email: EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ChatRequest(BaseModel):
    question: str
    user_id: int # どのユーザーのチャットボットか識別するため

class ChatResponse(BaseModel):
    answer: str

# --- パスワード関連の関数 ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- APIエンドポイント ---

# 1. 新規ユーザー登録API (変更なし)
@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    for db_user in fake_users_db:
        if db_user["email"] == user.email:
            raise HTTPException(status_code=400, detail="このメールアドレスは既に使用されています。")
    
    hashed_password = get_password_hash(user.password)
    new_user = {"id": len(fake_users_db) + 1, "company_name": user.company_name, "email": user.email, "hashed_password": hashed_password}
    fake_users_db.append(new_user)
    return new_user

# 2. ログインAPI (変更なし)
@app.post("/login", response_model=Token)
def login_for_access_token(form_data: UserLogin):
    user = next((u for u in fake_users_db if u["email"] == form_data.email), None)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが正しくありません。")
    access_token = f"dummy_token_for_user_{user['id']}"
    return {"access_token": access_token, "token_type": "bearer"}

# 3. PDFアップロードAPI (★asyncに変更★)
@app.post("/upload", status_code=status.HTTP_200_OK)
async def upload_pdf(user_id: int = Form(...), file: UploadFile = File(...)):
    # ユーザーが存在するか確認 (本来はトークンで認証)
    user = next((u for u in fake_users_db if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません。")

    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="PDFファイルのみアップロードできます。")

    try:
        # 1. PDFを非同期で読み込む
        pdf_bytes = await file.read()
        
        # PyPDFLoaderはファイルパスを要求するため、一時ファイルとして保存する
        temp_pdf_path = f"/tmp/{file.filename}"
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)
            
        loader = PyPDFLoader(temp_pdf_path)
        documents = loader.load()

        # 2. テキストを分割する
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)

        # 3. テキストをベクトル化し、DBに保存
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        vector_store = Chroma.from_documents(texts, embeddings)
        
        # ユーザーIDに紐づけてベクトルストアを保存
        vector_stores[user_id] = vector_store

        os.remove(temp_pdf_path) # 一時ファイルを削除

        return {"message": f"{file.filename} の読み込みが完了し、AIが学習しました。"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ファイルの処理中にエラーが発生しました: {e}")


# 4. チャットAPI (★asyncに変更★)
@app.post("/chat", response_model=ChatResponse)
async def chat_with_bot(request: ChatRequest):
    user_id = request.user_id
    question = request.question

    # ユーザーに紐づくベクトルストア（知識ベース）を取得
    vector_store = vector_stores.get(user_id)
    if not vector_store:
        raise HTTPException(status_code=404, detail="チャットボットの学習データが見つかりません。先にPDFをアップロードしてください。")

    try:
        # AIモデルを準備
        llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0, convert_system_message_to_human=True)
        
        # RAGチェーンを作成
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm,
            retriever=vector_store.as_retriever(),
            return_source_documents=False
        )
        
        # 質問を非同期で実行し、回答を取得
        result = await qa_chain.ainvoke({"question": question, "chat_history": []})
        
        return {"answer": result["answer"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回答の生成中にエラーが発生しました: {e}")


# 5. 登録ユーザー一覧API (動作確認用)
@app.get("/users", response_model=List[UserOut])
def read_users():
    return fake_users_db

# ルートURL
@app.get("/")
def read_root():
    return {"message": "ミミル バックエンドAPIへようこそ！"}
