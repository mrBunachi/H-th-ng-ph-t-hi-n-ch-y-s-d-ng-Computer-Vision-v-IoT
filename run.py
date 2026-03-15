import streamlit as st
import cv2
import time
import ssl
import tempfile
import paho.mqtt.client as mqtt
from ultralytics import YOLO
import uuid

# ================== CẤU HÌNH ==================

MODEL_PATH = "detect/train2/weights/best.pt"

# ================== MQTT (HiveMQ Cloud) ==================

MQTT_BROKER = "40f1a9b7ef1f4ae9b2855dff153c4fb7.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "Project3"
MQTT_PASS = "Project3"
MQTT_TOPIC = "aegis/fire_alarm"

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        st.session_state.mqtt_connected = True
        print("✅ [MQTT] KET NOI HIVE MQ THANH CONG!")
    else:
        print(f"❌ [MQTT] THAT BAI, code={reason_code}")

def on_publish(client, userdata, mid):
    print(f"📡 [MQTT] Da gui message id={mid}")

if "mqtt_client" not in st.session_state:
    # Tạo ID ngẫu nhiên để không bị trùng (Ví dụ: aegis-1234abc)
    random_id = f"aegis-{uuid.uuid4()}"
    
    client = mqtt.Client(
        client_id=random_id, 
        protocol=mqtt.MQTTv311
    )

    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_publish = on_publish

    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    print(f"Dang ket noi toi {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    st.session_state.mqtt_client = client
    st.session_state.mqtt_connected = False

# ================== STREAMLIT UI ==================

st.set_page_config(
    page_title="AEGIS Fire Guard",
    page_icon="🔥",
    layout="wide"
)

st.title("AEGIS HỆ THỐNG PHÁT HIỆN & CẢNH BÁO CHÁY")

# -------- SIDEBAR --------
st.sidebar.header("Cấu hình")

conf_threshold = st.sidebar.slider(
    "Độ nhạy phát hiện",
    min_value=0.0,
    max_value=1.0,
    value=0.5,
    step=0.05
)

source_option = st.sidebar.radio(
    "Nguồn video",
    ["Webcam", "File Video"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Trạng thái MQTT")

status_box = st.sidebar.empty()
if st.session_state.get("mqtt_connected"):
    status_box.success("Online (TLS)")
else:
    status_box.warning("Dang ket noi...")

# -------- TEST MQTT --------
st.sidebar.markdown("### Test nhanh MQTT")
col_a, col_b = st.sidebar.columns(2)

if col_a.button("Test ON"):
    if st.session_state.get("mqtt_client"):
        st.session_state.mqtt_client.publish(MQTT_TOPIC, "ON")
        st.toast("Da gui ON")

if col_b.button("Test OFF"):
    if st.session_state.get("mqtt_client"):
        st.session_state.mqtt_client.publish(MQTT_TOPIC, "OFF")
        st.toast("Da gui OFF")

# ================== LOAD MODEL ==================

@st.cache_resource
def load_model():
    try:
        return YOLO(MODEL_PATH)
    except:
        st.warning("⚠️ Khong tim thay model, dung yolov8s.pt")
        return YOLO("yolov8s.pt")

model = load_model()

# ================== MAIN LAYOUT ==================

col1, col2 = st.columns([3, 1])

with col2:
    st.subheader("Nhat ky")
    log_box = st.empty()
    stop_btn = st.button("DUNG", type="primary")

with col1:
    cap = None

    if source_option == "Webcam":
        if st.button("Bat Webcam"):
            cap = cv2.VideoCapture(0)
    else:
        uploaded = st.file_uploader("Chon video", type=["mp4", "avi"])
        if uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            tmp.write(uploaded.read())
            cap = cv2.VideoCapture(tmp.name)

    if cap and cap.isOpened():
        frame_box = st.empty()
        last_state = "SAFE"
        
        # --- CẤU HÌNH THỜI GIAN ---
        prev_time = 0
        CHECK_INTERVAL = 2.0
        
        # Biến lưu kết quả cũ
        last_results = None 

        while cap.isOpened() and not stop_btn:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Tính toán thời gian hiện tại
            current_time = time.time()
            
            # --- LOGIC QUAN TRỌNG: CHỈ CHẠY AI SAU MỖI 2 GIÂY ---
            if current_time - prev_time > CHECK_INTERVAL:
                
                # 1. Chạy nhận diện
                results = model(frame, conf=conf_threshold, verbose=False)
                last_results = results 
                prev_time = current_time 
                
                # 2. Xử lý Logic Báo Cháy
                is_fire = False
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        current_class_name = model.names[cls_id]
                        
                        target_classes = ['fire', 'flame', 'chay'] 
                        if current_class_name.lower() in target_classes:
                            is_fire = True
                            break 
                    if is_fire: break

                # 3. Gửi MQTT (Chỉ gửi khi trạng thái thay đổi)
                current_state = "FIRE" if is_fire else "SAFE"

                if current_state != last_state:
                    msg = "ON" if is_fire else "OFF"

                    if st.session_state.get("mqtt_client"):
                        st.session_state.mqtt_client.publish(MQTT_TOPIC, msg)
                        print(f"MQTT GUI: {msg}")

                    if is_fire:
                        log_box.error(f"[{time.strftime('%H:%M:%S')}] PHAT HIEN CHAY!")
                    else:
                        log_box.success(f"[{time.strftime('%H:%M:%S')}] AN TOAN")

                    last_state = current_state

            # --- HIỂN THỊ VIDEO ---
            if last_results:
                res_plotted = last_results[0].plot(img=frame)
                frame_display = res_plotted
            else:
                frame_display = frame

            # SỬA LỖI 1: Thay use_container_width bằng width="stretch"
            frame_box.image(
                cv2.cvtColor(frame_display, cv2.COLOR_BGR2RGB),
                channels="RGB",
                width="stretch" 
            )

            # SỬA LỖI 2: Thêm phanh để giảm tải CPU (0.03s ~ 30 FPS)
            time.sleep(0.03)

        cap.release()