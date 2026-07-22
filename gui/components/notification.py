import customtkinter as ctk

class UXNotification:
    @staticmethod
    def render_popup(parent, title, message):
        popup = ctk.CTkToplevel(parent)
        popup.title(title)
        popup.geometry("400x150")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.configure(fg_color="#1A1A1E")
        
        ctk.CTkLabel(popup, text=message, font=ctk.CTkFont("Segoe UI", 12), wraplength=350, text_color="#E0E0E6").pack(expand=True, padx=20, pady=(20, 10))
        ctk.CTkButton(popup, text="Acknowledge", width=110, font=ctk.CTkFont("Segoe UI", 12, "bold"), fg_color="#3A7DFF", hover_color="#2A65D4", command=popup.destroy).pack(pady=(0, 20))
