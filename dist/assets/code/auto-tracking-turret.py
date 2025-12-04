import cv2
import mediapipe as mp
import serial
import time
from collections import deque
import math

SERIAL_PORT = "COM3"
BAUDRATE = 115200


# -----------------------------------------
#  DITO ALZATO (tip sopra pip)
# -----------------------------------------
def finger_up(hand, tip_id, pip_id):
    tip = hand.landmark[tip_id]
    pip = hand.landmark[pip_id]
    return tip.y < pip.y   # se la punta è più in alto → dito alzato


# -----------------------------------------
#  ZOOM DIGITALE
# -----------------------------------------
def apply_zoom(frame, z):
    if z <= 1.0:
        return frame

    h, w, _ = frame.shape
    new_w = int(w / z)
    new_h = int(h / z)

    x1 = (w - new_w) // 2
    y1 = (h - new_h) // 2

    crop = frame[y1:y1+new_h, x1:x1+new_w]
    return cv2.resize(crop, (w, h))


# =============================
#         MAIN PROGRAM
# =============================
def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    time.sleep(2)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    mp_holistic = mp.solutions.holistic
    holistic = mp_holistic.Holistic(
        model_complexity=1,
        refine_face_landmarks=True,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    # ---- SERVO ----
    angle = 90
    angle_min, angle_max = 30, 150
    filtro = deque(maxlen=5)
    max_step = 6
    dead_zone = 0.10
    power = 1.8

    # ---- HOLD MODE ----
    hold_mode = False
    prev_toggle_open = False   # per il rising edge del gesto di toggle

    # ---- ZOOM ----
    zoom_factor = 1.0
    ZOOM_MIN = 1.0
    ZOOM_MAX = 3.0
    ZOOM_SPEED = 0.18      # zoom veloce
    zoom_smooth = deque(maxlen=5)

    print("[INFO] Sistema attivo.")


    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = holistic.process(rgb)

        right = results.right_hand_landmarks

        # ==========================
        #       GESTURE MANO DX
        # ==========================
        did_toggle = False
        if right:
            # stato dita
            index_up  = finger_up(right, 8, 6)
            middle_up = finger_up(right, 12, 10)
            ring_up   = finger_up(right, 16, 14)
            pinky_up  = finger_up(right, 20, 18)

            # ---- GESTO TOGGLE: palmo aperto (indice+medio+anulare+mignolo su) ----
            toggle_open = index_up and middle_up and ring_up and pinky_up

            if toggle_open and not prev_toggle_open:
                hold_mode = not hold_mode
                did_toggle = True   # in questo frame NON facciamo zoom

            prev_toggle_open = toggle_open

            # ---- GESTI ZOOM (solo se NON è il gesto di toggle) ----
            if not toggle_open and not did_toggle:
                # Zoom IN: solo indice alzato
                if index_up and not middle_up and not ring_up and not pinky_up:
                    zoom_factor += ZOOM_SPEED

                # Zoom OUT: indice + medio alzati
                if index_up and middle_up and not ring_up and not pinky_up:
                    zoom_factor -= ZOOM_SPEED

                zoom_factor = max(ZOOM_MIN, min(ZOOM_MAX, zoom_factor))
                zoom_smooth.append(zoom_factor)
                zoom_factor = sum(zoom_smooth) / len(zoom_smooth)

        # ---------------------------------------------------------
        # VISUAL FEEDBACK
        # ---------------------------------------------------------
        mode_text = "HOLD" if hold_mode else "TRACK"
        color = (0, 0, 255) if hold_mode else (0, 255, 0)

        cv2.putText(frame, f"{mode_text}  Zoom:{zoom_factor:.2f}x",
                    (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)


        # =====================================================
        #              HOLD → servo fermo
        # =====================================================
        if hold_mode:
            show = apply_zoom(frame, zoom_factor)
            cv2.imshow("Tracking + Zoom", show)
            if cv2.waitKey(1) & 0xFF in (27, ord('q')):
                break
            continue


        # =====================================================
        #              TRACKING (naso + busto)
        # =====================================================
        x_norm = None
        used_fallback = False

        # Naso
        if results.face_landmarks:
            nose = results.face_landmarks.landmark[1]
            x_norm = nose.x
            cv2.circle(frame, (int(nose.x*w), int(nose.y*h)),
                       8, (0,255,0), -1)

        # Fallback busto
        if x_norm is None:
            if results.pose_landmarks:
                ls = results.pose_landmarks.landmark[11]
                rs = results.pose_landmarks.landmark[12]

                if ls.visibility > 0.4 and rs.visibility > 0.4:
                    x_norm = (ls.x + rs.x) / 2
                    used_fallback = True

        # Movimento servo
        if x_norm is not None:
            filtro.append(x_norm)
            x_filt = sum(filtro) / len(filtro)

            error = -(x_filt - 0.5)

            if abs(error) > dead_zone:
                ratio = min(abs(error) / 0.5, 1.0)
                step = max_step * (ratio ** power)
                angle += step if error > 0 else -step

        angle = max(angle_min, min(angle_max, angle))
        ser.write(f"ANGLE:{int(angle)}\n".encode())

        # ==========================
        #   ZOOM DISPLAY
        # ==========================
        show = apply_zoom(frame, zoom_factor)
        cv2.imshow("Tracking + Zoom", show)

        if cv2.waitKey(1) & 0xFF in (27, ord('q')):
            break


    cap.release()
    cv2.destroyAllWindows()
    ser.close()


if __name__ == "__main__":
    main()
