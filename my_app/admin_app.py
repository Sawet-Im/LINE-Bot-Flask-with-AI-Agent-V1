# my_app/admin_app.py
import streamlit as st
import requests
import os
from database import initialize_database, get_tasks_by_status, update_task_status, get_credentials
from linebot import LineBotApi
from linebot.models import TextSendMessage
from dotenv import load_dotenv

load_dotenv()

# --- Page Setup ---
st.set_page_config(page_title="Admin Dashboard", layout="wide")
st.title("🤖 Admin Dashboard: Review AI Responses")
st.write("ตรวจสอบและแก้ไขคำตอบของ AI ก่อนส่งให้ลูกค้า")

# --- Initialize Database ---
db_uri = initialize_database()

# --- Helper functions ---
@st.cache_data
def get_user_profile(user_id):
    """Fetches user profile (name and picture) from LINE API."""
    credentials_data = get_credentials(user_id)
    if not credentials_data:
        print(f"Credentials not found for user: {user_id}")
        return user_id, None
    
    line_bot_api = LineBotApi(credentials_data['channel_access_token'])
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.display_name, profile.picture_url
    except Exception as e:
        print(f"Error fetching user profile for {user_id}: {e}")
        return user_id, None

def send_line_message(user_id, message):
    """Sends a message back to the user via LINE Push API using the correct token."""
    credentials_data = get_credentials(user_id)
    if not credentials_data:
        st.error(f"ไม่พบข้อมูล Channel API สำหรับผู้ใช้: {user_id}")
        return False
    
    line_bot_api = LineBotApi(credentials_data['channel_access_token'])
    try:
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=message)
        )
        return True
    except Exception as e:
        print(f"Error sending message to {user_id}: {e}")
        return False

# --- Main UI for Awaiting Approval Tasks ---
st.header("ข้อความที่รอการอนุมัติ")
tasks = get_tasks_by_status("Awaiting_Approval")

if not tasks:
    st.info("ไม่มีข้อความที่รอการอนุมัติในขณะนี้")
else:
    for task in tasks:
        # Note: We assume 'line_id' in tasks table is our unique 'user_id'
        user_id = task['line_id']
        with st.expander(f"ข้อความจากลูกค้า"):
            user_name, user_pic = get_user_profile(user_id)
            
            # Display user profile
            st.markdown("---")
            col1, col2 = st.columns([1, 4])
            with col1:
                if user_pic:
                    st.image(user_pic, width=80)
                else:
                    st.image("https://placehold.co/80x80/cccccc/000000?text=No+Img", width=80)
            with col2:
                st.subheader(f"{user_name}")
                st.caption(f"Line ID: {user_id}")
                st.caption(f"เวลา: {task['timestamp']}")
            st.markdown("---")
            
            # Display original message
            st.markdown(f"**ข้อความจากลูกค้า:** `{task['user_message']}`")
            
            # Split AI response to remove SQL command
            ai_response_full = task['ai_response'] if task['ai_response'] else ""
            if "คำสั่ง SQL ที่ใช้:" in ai_response_full:
                ai_response = ai_response_full.split("คำสั่ง SQL ที่ใช้:")[0].strip()
            else:
                ai_response = ai_response_full
            
            # Editable text area for admin to review/edit
            edited_response = st.text_area(
                "คำตอบที่แก้ไข",
                value=task['admin_response'] if task['admin_response'] else ai_response,
                key=f"editor_{task['task_id']}"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("บันทึกและส่งข้อความ", key=f"save_{task['task_id']}"):
                    final_response = edited_response
                    if send_line_message(user_id, final_response):
                        update_task_status(task['task_id'], "Sent")
                        st.success("ส่งข้อความสำเร็จ! สถานะอัปเดตแล้ว")
                        st.rerun()
                    else:
                        st.error("เกิดข้อผิดพลาดในการส่งข้อความ LINE")
            with col2:
                if st.button("อนุมัติและส่งข้อความ", key=f"approve_{task['task_id']}"):
                    final_response = edited_response
                    if send_line_message(user_id, final_response):
                        update_task_status(task['task_id'], "Sent")
                        st.success("ส่งข้อความสำเร็จ! สถานะอัปเดตแล้ว")
                        st.rerun()
                    else:
                        st.error("เกิดข้อผิดพลาดในการส่งข้อความ LINE")
            
            if st.button("ปฏิเสธ (ยกเลิกงาน)", key=f"reject_{task['task_id']}"):
                update_task_status(task['task_id'], "Rejected")
                st.warning("งานถูกปฏิเสธแล้ว")
                st.rerun()
