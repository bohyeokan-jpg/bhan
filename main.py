import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
from plyer import notification
import json
import os
from datetime import datetime
import threading
import time
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
import tempfile


DATA_FILE = "schedules.json"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(schedules):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


class ScheduleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("스케줄 관리")
        self.root.geometry("800x600")
        self.schedules = load_data()

        self._build_ui()
        self._start_alarm_thread()

    def _build_ui(self):
        # 왼쪽: 달력
        left = tk.Frame(self.root, padx=10, pady=10)
        left.pack(side="left", fill="y")

        self.cal = Calendar(left, selectmode="day", date_pattern="yyyy-mm-dd",
                            font="Arial 11", locale="ko_KR")
        self.cal.pack()
        self.cal.bind("<<CalendarSelected>>", self._on_date_select)

        tk.Button(left, text="이 날짜에 일정 추가", command=self._open_add_dialog,
                  width=20).pack(pady=8)

        # 오른쪽: 일정 목록
        right = tk.Frame(self.root, padx=10, pady=10)
        right.pack(side="left", fill="both", expand=True)

        self.date_label = tk.Label(right, text="날짜를 선택하세요", font="Arial 13 bold")
        self.date_label.pack(anchor="w")

        columns = ("시간", "내용")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", height=20)
        self.tree.heading("시간", text="시간")
        self.tree.heading("내용", text="내용")
        self.tree.column("시간", width=80)
        self.tree.column("내용", width=320)
        self.tree.pack(fill="both", expand=True, pady=5)

        tk.Button(right, text="선택 삭제", command=self._delete_schedule,
                  width=12).pack(anchor="w")

        self._refresh_calendar_marks()

    def _on_date_select(self, event=None):
        date = self.cal.get_date()
        self.date_label.config(text=f"{date} 일정")
        self._load_list(date)

    def _load_list(self, date):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for s in sorted(self.schedules, key=lambda x: x["time"]):
            if s["date"] == date:
                self.tree.insert("", "end", iid=s["id"], values=(s["time"], s["content"]))

    def _open_add_dialog(self):
        date = self.cal.get_date()
        dialog = tk.Toplevel(self.root)
        dialog.title("일정 추가")
        dialog.geometry("380x220")
        dialog.grab_set()

        tk.Label(dialog, text=f"날짜: {date}", font="Arial 11").pack(pady=5)

        row1 = tk.Frame(dialog)
        row1.pack(fill="x", padx=20, pady=3)
        tk.Label(row1, text="시간 (HH:MM):", width=14, anchor="w").pack(side="left")
        time_entry = tk.Entry(row1, width=10)
        time_entry.pack(side="left")
        time_entry.insert(0, datetime.now().strftime("%H:%M"))

        row2 = tk.Frame(dialog)
        row2.pack(fill="x", padx=20, pady=3)
        tk.Label(row2, text="내용:", width=14, anchor="w").pack(side="left")
        content_entry = tk.Entry(row2, width=22)
        content_entry.pack(side="left")

        # 음성 입력 버튼
        self.mic_status = tk.StringVar(value="")
        tk.Label(dialog, textvariable=self.mic_status, fg="blue").pack()

        def record_voice():
            mic_btn.config(state="disabled", text="녹음 중...")
            self.mic_status.set("말씀하세요...")

            def do_record():
                try:
                    samplerate = 16000
                    duration = 5  # 5초 녹음
                    audio = sd.rec(int(samplerate * duration),
                                   samplerate=samplerate, channels=1, dtype="int16")
                    sd.wait()

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        wav.write(f.name, samplerate, audio)
                        tmp_path = f.name

                    recognizer = sr.Recognizer()
                    with sr.AudioFile(tmp_path) as source:
                        audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language="ko-KR")

                    content_entry.delete(0, "end")
                    content_entry.insert(0, text)
                    self.mic_status.set(f"인식됨: {text}")
                except sr.UnknownValueError:
                    self.mic_status.set("음성을 인식하지 못했어요.")
                except Exception as e:
                    self.mic_status.set(f"오류: {e}")
                finally:
                    mic_btn.config(state="normal", text="마이크로 입력")
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            threading.Thread(target=do_record, daemon=True).start()

        mic_btn = tk.Button(dialog, text="마이크로 입력", command=record_voice, width=16, bg="#e0f0ff")
        mic_btn.pack(pady=3)

        def save():
            t = time_entry.get().strip()
            c = content_entry.get().strip()
            if not t or not c:
                messagebox.showwarning("입력 오류", "시간과 내용을 입력하세요.", parent=dialog)
                return
            uid = f"{date}_{t}_{len(self.schedules)}"
            self.schedules.append({"id": uid, "date": date, "time": t, "content": c, "notified": False})
            save_data(self.schedules)
            self._load_list(date)
            self._refresh_calendar_marks()
            dialog.destroy()

        tk.Button(dialog, text="저장", command=save, width=10).pack(pady=5)

    def _delete_schedule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 오류", "삭제할 항목을 선택하세요.")
            return
        for iid in selected:
            self.schedules = [s for s in self.schedules if s["id"] != iid]
        save_data(self.schedules)
        self._load_list(self.cal.get_date())
        self._refresh_calendar_marks()

    def _refresh_calendar_marks(self):
        self.cal.calevent_remove("all")
        dates = set(s["date"] for s in self.schedules)
        for d in dates:
            try:
                self.cal.calevent_create(datetime.strptime(d, "%Y-%m-%d"), "일정", "schedule")
            except Exception:
                pass
        self.cal.tag_config("schedule", background="skyblue", foreground="black")

    def _start_alarm_thread(self):
        def check_alarms():
            while True:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                for s in self.schedules:
                    if not s.get("notified") and f"{s['date']} {s['time']}" == now:
                        notification.notify(
                            title="스케줄 알림",
                            message=s["content"],
                            timeout=10
                        )
                        s["notified"] = True
                        save_data(self.schedules)
                time.sleep(30)

        threading.Thread(target=check_alarms, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = ScheduleApp(root)
    root.mainloop()
