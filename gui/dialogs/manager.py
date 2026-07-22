import customtkinter as ctk
from tkinter import ttk
import tkinter as tk

class SessionManagerWindow(ctk.CTkToplevel):
    """
    Dialog for managing and loading previous telemetry sessions.
    """
    def __init__(self, parent, db_manager, on_load_callback):
        super().__init__(parent)
        self.title("Session Manager")
        self.geometry("700x500")
        self.minsize(600, 400)
        
        self.db = db_manager
        self.on_load = on_load_callback
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self._build_ui()
        self._refresh_list()
        
    def _build_ui(self):
        # Toolbar
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        self.search_entry = ctk.CTkEntry(self.toolbar, placeholder_text="Search sessions...", width=250)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_list())
        
        self.btn_refresh = ctk.CTkButton(self.toolbar, text="Refresh", width=80, command=self._refresh_list)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_rename = ctk.CTkButton(self.toolbar, text="Rename", width=80, fg_color="#E1B12C", hover_color="#c49b25", command=self._action_rename)
        self.btn_rename.pack(side="right", padx=5)
        
        self.btn_delete = ctk.CTkButton(self.toolbar, text="Delete", width=80, fg_color="#D73A49", hover_color="#cb2431", command=self._action_delete)
        self.btn_delete.pack(side="right", padx=5)
        
        self.btn_load = ctk.CTkButton(self.toolbar, text="Load Data", width=100, fg_color="#2EA44F", hover_color="#2c974b", command=self._action_load)
        self.btn_load.pack(side="right", padx=5)
        
        # Treeview (using tk/ttk since ctk doesn't have a data grid yet)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#1E1E24", foreground="white", fieldbackground="#1E1E24", borderwidth=0, rowheight=30)
        style.map('Treeview', background=[('selected', '#3A7DFF')])
        style.configure("Treeview.Heading", background="#2C2C34", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#3A7DFF')])
        
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        
        columns = ("session_id", "name", "start_time", "burst_count", "status", "source_type")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings", style="Treeview")
        
        self.tree.heading("session_id", text="Session ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("start_time", text="Created")
        self.tree.heading("burst_count", text="Bursts")
        self.tree.heading("status", text="Status")
        self.tree.heading("source_type", text="Source")
        
        self.tree.column("session_id", width=120)
        self.tree.column("name", width=150)
        self.tree.column("start_time", width=150)
        self.tree.column("burst_count", width=80)
        self.tree.column("status", width=80)
        self.tree.column("source_type", width=80)
        
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", lambda e: self._action_load())

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        search_term = self.search_entry.get()
        if not search_term:
            search_term = None
            
        sessions = self.db.get_all_sessions(search_term)
        for session in sessions:
            self.tree.insert("", "end", values=session)

    def _get_selected_id(self):
        selection = self.tree.selection()
        if not selection:
            return None
        item = self.tree.item(selection[0])
        return item['values'][0]

    def _action_load(self):
        session_id = self._get_selected_id()
        if session_id:
            self.on_load(f"({session_id})") # formatted as needed by main app, or directly
            self.destroy()

    def _action_rename(self):
        session_id = self._get_selected_id()
        if session_id:
            dialog = ctk.CTkInputDialog(text="Enter new name:", title="Rename Session")
            new_name = dialog.get_input()
            if new_name:
                self.db.rename_session(session_id, new_name)
                self._refresh_list()

    def _action_delete(self):
        session_id = self._get_selected_id()
        if session_id:
            # Simple confirmation could go here
            self.db.delete_session(session_id)
            self._refresh_list()
