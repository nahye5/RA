import streamlit as st
import openai
import time
import json
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="문서 기반 AI 챗봇",
    page_icon="📚",
    layout="wide"
)

# API 키 설정 (환경변수 또는 직접 입력)
# 방법 1: 환경변수에서 가져오기
api_key = os.getenv("OPENAI_API_KEY")

# 방법 2: 직접 코드에 입력 (보안상 권장하지 않음)
# api_key = "your-api-key-here"

# 기존 Assistant ID 설정 (선택사항)
EXISTING_ASSISTANT_ID = "asst_nPcXHjfN0G8nFcpWPxo08byE"  # 기존 Assistant 사용 시

# 사이드바 설정
with st.sidebar:
    st.title("📚 문서 기반 AI 챗봇")
    
    # API 키 상태 표시
    if api_key:
        st.success("✅ API 키가 설정되었습니다")
    else:
        st.error("❌ API 키를 설정해주세요")
        st.markdown("""
        **API 키 설정 방법:**
        1. 환경변수로 설정: `OPENAI_API_KEY=your-key`
        2. 코드에서 직접 설정 (16번째 줄)
        """)
    
    st.markdown("---")
    
    # 파일 업로드
    st.subheader("📄 문서 업로드")
    uploaded_file = st.file_uploader(
        "Markdown 파일을 업로드하세요",
        type=['md'],
        help="업로드된 문서를 기반으로만 답변합니다"
    )
    
    # Assistant 모드 선택
    st.subheader("🤖 Assistant 모드")
    assistant_mode = st.radio(
        "Assistant 모드 선택",
        ["기존 Assistant 사용", "새 Assistant 생성"],
        help="기존 Assistant를 사용하거나 새로 생성할 수 있습니다"
    )
    
    if assistant_mode == "기존 Assistant 사용":
        st.info(f"🔗 기존 Assistant ID: `{EXISTING_ASSISTANT_ID}`")
        st.markdown(f"[Dashboard에서 확인](https://platform.openai.com/assistants/{EXISTING_ASSISTANT_ID})")
    else:
        # Assistant 설정 (새 생성 시에만)
        st.subheader("🤖 새 Assistant 설정")
        assistant_name = st.text_input("Assistant 이름", value="문서 전문가")
        
        # 모델 선택
        model_choice = st.selectbox(
            "모델 선택",
            ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
        )
    
    # 새 대화 시작
    if st.button("새 대화 시작"):
        # 새 Assistant 생성 모드에서만 기존 assistant 삭제
        if (assistant_mode == "새 Assistant 생성" and 
            hasattr(st.session_state, 'assistant_id') and 
            st.session_state.assistant_id and 
            st.session_state.assistant_id != EXISTING_ASSISTANT_ID):
            try:
                client = openai.OpenAI(api_key=api_key)
                client.beta.assistants.delete(st.session_state.assistant_id)
            except:
                pass
        
        # 세션 상태 초기화
        for key in list(st.session_state.keys()):
            if key != 'uploaded_file_content':
                del st.session_state[key]
        st.rerun()

# 메인 페이지
st.title("📚 문서 기반 AI 챗봇")
st.markdown("업로드된 Markdown 문서를 기반으로만 답변하는 AI 챗봇입니다.")

# API 키 확인
if not api_key:
    st.error("❌ OpenAI API 키가 설정되지 않았습니다.")
    st.markdown("""
    **API 키 설정 방법:**
    
    **방법 1: 환경변수 사용 (권장)**
    ```bash
    export OPENAI_API_KEY="your-api-key-here"
    streamlit run chatbot_app.py
    ```
    
    **방법 2: 코드에서 직접 설정**
    ```python
    # 코드 16번째 줄에서 설정
    api_key = "your-api-key-here"
    ```
    """)
    st.stop()

# OpenAI 클라이언트 초기화
try:
    client = openai.OpenAI(api_key=api_key)
except Exception as e:
    st.error(f"OpenAI 클라이언트 초기화 실패: {e}")
    st.stop()

# 파일 업로드 확인
if not uploaded_file:
    st.warning("⚠️ 사이드바에서 Markdown 파일을 업로드해주세요.")
    st.info("📝 업로드된 문서만을 기반으로 답변합니다.")
    st.stop()

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "file_id" not in st.session_state:
    st.session_state.file_id = None

# 파일 업로드 및 Assistant 설정
def setup_assistant():
    # 기존 Assistant 사용 모드
    if assistant_mode == "기존 Assistant 사용":
        try:
            # 기존 Assistant 정보 확인
            with st.spinner("기존 Assistant 정보를 확인하는 중..."):
                assistant = client.beta.assistants.retrieve(EXISTING_ASSISTANT_ID)
                st.session_state.assistant_id = EXISTING_ASSISTANT_ID
                st.success(f"✅ 기존 Assistant '{assistant.name}' 연결 완료!")
                
                # 파일이 업로드된 경우에만 새 vector store 생성
                if uploaded_file:
                    return upload_file_to_existing_assistant()
                else:
                    return True
                    
        except Exception as e:
            st.error(f"기존 Assistant 연결 실패: {e}")
            return False
    
    # 새 Assistant 생성 모드
    else:
        return upload_file_and_create_assistant()

def upload_file_to_existing_assistant():
    """기존 Assistant에 새 파일 업로드"""
    try:
        # 파일 내용 읽기
        file_content = uploaded_file.read()
        
        # OpenAI에 파일 업로드
        with st.spinner("파일을 업로드하는 중..."):
            uploaded_openai_file = client.files.create(
                file=(uploaded_file.name, file_content),
                purpose='assistants'
            )
            st.session_state.file_id = uploaded_openai_file.id
        
        # 기존 Assistant 업데이트 (새 파일 추가)
        with st.spinner("Assistant에 파일을 추가하는 중..."):
            client.beta.assistants.update(
                assistant_id=EXISTING_ASSISTANT_ID,
                tool_resources={
                    "file_search": {
                        "vector_stores": [
                            {
                                "file_ids": [st.session_state.file_id]
                            }
                        ]
                    }
                }
            )
        
        st.success(f"✅ 기존 Assistant에 파일 '{uploaded_file.name}' 추가 완료!")
        return True
        
    except Exception as e:
        st.error(f"파일 업로드 실패: {e}")
        return False
    try:
        # 파일 내용 읽기
        file_content = uploaded_file.read()
        
        # OpenAI에 파일 업로드
        with st.spinner("파일을 업로드하는 중..."):
            uploaded_openai_file = client.files.create(
                file=(uploaded_file.name, file_content),
                purpose='assistants'
            )
            st.session_state.file_id = uploaded_openai_file.id
        
        # Assistant 생성 시 사용할 지시사항
        instructions = f"""
        당신은 업로드된 문서의 전문가입니다. 다음 규칙을 엄격히 따라주세요:

        1. 오직 업로드된 문서의 내용만을 기반으로 답변하세요.
        2. 문서에 없는 내용에 대해서는 "해당 내용은 업로드된 문서에서 찾을 수 없습니다"라고 답변하세요.
        3. 문서의 내용을 정확히 인용하고, 가능하면 해당 섹션을 명시하세요.
        4. 문서 외의 일반적인 지식을 사용하지 마세요.
        5. 답변할 때는 문서에서 관련된 부분을 먼저 찾아 확인한 후 답변하세요.
        6. 불확실한 경우 문서를 다시 확인하세요.
        
        업로드된 문서 파일: {uploaded_file.name}
        """
        
        # Assistant 생성
        with st.spinner("Assistant를 생성하는 중..."):
            assistant = client.beta.assistants.create(
                name=assistant_name,
                instructions=instructions,
                model=model_choice,
                tools=[{"type": "file_search"}],
                tool_resources={
                    "file_search": {
                        "vector_stores": [
                            {
                                "file_ids": [st.session_state.file_id]
                            }
                        ]
                    }
                }
            )
            st.session_state.assistant_id = assistant.id
        
        st.success(f"✅ 파일 '{uploaded_file.name}' 업로드 및 Assistant 생성 완료!")
        
    except Exception as e:
        st.error(f"파일 업로드 또는 Assistant 생성 실패: {e}")
        return False
    
    return True

# Thread 생성
def create_thread():
    try:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        return True
    except Exception as e:
        st.error(f"Thread 생성 실패: {e}")
        return False

# 메시지 전송 및 응답 받기
def send_message(message):
    try:
        # 메시지 추가
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=message
        )
        
        # Run 생성
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=st.session_state.assistant_id
        )
        
        # Run 완료 대기
        with st.spinner("문서를 검색하고 답변을 생성하는 중..."):
            while True:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    break
                elif run_status.status == "failed":
                    st.error("답변 생성에 실패했습니다.")
                    return None
                elif run_status.status == "requires_action":
                    st.error("추가 작업이 필요합니다.")
                    return None
                
                time.sleep(1)
        
        # 응답 메시지 가져오기
        messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        latest_message = messages.data[0]
        
        if latest_message.role == "assistant":
            return latest_message.content[0].text.value
        
    except Exception as e:
        st.error(f"메시지 전송 실패: {e}")
        return None

# Assistant 및 Thread 초기화
if st.session_state.assistant_id is None:
    if not setup_assistant():
        st.stop()
else:
    # 파일이 새로 업로드된 경우 파일 추가
    if uploaded_file and not st.session_state.file_id:
        if assistant_mode == "기존 Assistant 사용":
            if not upload_file_to_existing_assistant():
                st.stop()
        else:
            if not upload_file_and_create_assistant():
                st.stop()

if st.session_state.thread_id is None:
    if not create_thread():
        st.stop()

# 파일 정보 표시
if st.session_state.assistant_id == EXISTING_ASSISTANT_ID:
    st.info(f"🔗 **기존 Assistant 사용 중**: `{EXISTING_ASSISTANT_ID}`")
    if uploaded_file:
        st.info(f"📄 **추가된 문서**: {uploaded_file.name}")
else:
    if st.session_state.file_id:
        st.info(f"📄 **현재 사용 중인 문서**: {uploaded_file.name}")
    
# Assistant 정보 표시 링크
if st.session_state.assistant_id:
    st.markdown(f"[📊 Dashboard에서 Assistant 확인](https://platform.openai.com/assistants/{st.session_state.assistant_id})")

# 채팅 히스토리 표시
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "timestamp" in message:
                st.caption(f"🕐 {message['timestamp']}")

# 사용자 입력
if prompt := st.chat_input("문서에 대해 질문해보세요..."):
    # 사용자 메시지 추가
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt,
        "timestamp": timestamp
    })
    
    # 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(prompt)
        st.caption(f"🕐 {timestamp}")
    
    # Assistant 응답 받기
    response = send_message(prompt)
    
    if response:
        # Assistant 응답 추가
        response_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response,
            "timestamp": response_timestamp
        })
        
        # Assistant 응답 표시
        with st.chat_message("assistant"):
            st.markdown(response)
            st.caption(f"🕐 {response_timestamp}")

# 하단 정보
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("총 메시지", len(st.session_state.messages))

with col2:
    if st.session_state.assistant_id:
        st.success("Assistant 활성화")
    else:
        st.error("Assistant 비활성화")

with col3:
    if st.session_state.thread_id:
        st.success("Thread 활성화")
    else:
        st.error("Thread 비활성화")

with col4:
    if st.session_state.file_id:
        st.success("문서 업로드됨")
    else:
        st.error("문서 없음")

# 사용법 안내
with st.expander("📖 사용법"):
    st.markdown("""
    **문서 기반 챗봇 사용법:**
    
    1. **API 키 설정**: 환경변수 또는 코드에서 직접 설정
    2. **Assistant 모드 선택**: 
       - 기존 Assistant 사용: `asst_nPcXHjfN0G8nFcpWPxo08byE`
       - 새 Assistant 생성: 커스텀 설정으로 새로 생성
    3. **문서 업로드**: 사이드바에서 .md 파일 업로드 (선택사항)
    4. **질문하기**: 업로드된 문서 내용 또는 Assistant 지식 기반으로 답변
    5. **새 문서**: 새 문서 사용 시 "새 대화 시작" 클릭
    
    **특징:**
    - 기존 Assistant: 이미 설정된 지시사항과 파일 사용
    - 새 Assistant: 업로드된 문서만을 기반으로 답변
    - File Search 기능으로 정확한 검색
    - 문서 내용 인용 및 참조
    
    **Assistant ID 정보:**
    - 현재 설정된 ID: `asst_nPcXHjfN0G8nFcpWPxo08byE`
    - [Dashboard에서 확인](https://platform.openai.com/assistants/asst_nPcXHjfN0G8nFcpWPxo08byE)
    
    **주의사항:**
    - 문서 외의 일반 지식은 사용하지 않음
    - 대용량 문서는 처리 시간이 오래 걸릴 수 있음
    """)

# 디버깅 정보
if st.checkbox("디버그 정보 표시"):
    st.json({
        "assistant_id": st.session_state.assistant_id,
        "thread_id": st.session_state.thread_id,
        "file_id": st.session_state.file_id,
        "message_count": len(st.session_state.messages),
        "uploaded_file": uploaded_file.name if uploaded_file else None,
        "api_key_set": bool(api_key)
    })