# Session management console for viewing, renaming, loading, and deleting
# recorded telemetry sessions from the SQLite database.

import customtkinter as ctk
from tkinter import messagebox, simpledialog, ttk


class SessionManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent, db_manager, on_session_load_callback):
        super().__init__(parent)
        self.parent = parent
        self.db = db_manager
        self.load_callback = on_session_load_callback
        
        self.title("Session Management Console")
        self.geometry("750x500")
        self.minsize(700, 400)
        
        # Configure transient window settings for Linux compatibility (avoids hiding under main app)
        self.transient(parent)
        self.after(100, self.focus_force)
        self.after(100, self.grab_set)
        
        # Main Grid Config
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._build_top_bar()
        self._build_list_container()
        self.refresh_session_list()

    def _build_top_bar(self):
        top_bar = ctk.CTkFrame(self, fg_color="transparent", height=60)
        top_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        top_bar.grid_columnconfigure(0, weight=1)
        
        # Search Entry Bar
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_session_list())
        
        search_entry = ctk.CTkEntry(
            top_bar, placeholder_text="Search sessions by code index or tag identity...", 
            textvariable=self.search_var, height=35
        )
        search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        # Refresh Button
        btn_refresh = ctk.CTkButton(
            top_bar, text="Refresh", width=90, height=35, 
            fg_color="#2D2D34", hover_color="#3A3A42", command=self.refresh_session_list
        )
        btn_refresh.grid(row=0, column=1)

    def _build_list_container(self):
        # Configure native style for ttk.Treeview and Scrollbar to match dark theme
        style = ttk.Style(self)
        style.theme_use("clam")
        
        # Style treeview rows
        style.configure(
            "Custom.Treeview",
            background="#1C1C21",
            foreground="#FFFFFF",
            fieldbackground="#141416",
            rowheight=35,
            font=("Segoe UI", 11),
            borderwidth=0,
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", "#3A7DFF")],
            foreground=[("selected", "#FFFFFF")],
        )
        
        # Style headers
        style.configure(
            "Custom.Treeview.Heading",
            background="#1A1A1E",
            foreground="#7F7F8C",
            font=("Segoe UI", 11, "bold"),
            borderwidth=0,
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[("active", "#25252A")],
            foreground=[("active", "#FFFFFF")],
        )
 
        # Style scrollbar
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background="#2D2D34",
            troughcolor="#141416",
            bordercolor="#141416",
            arrowcolor="#FFFFFF",
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", "#3A3A42")],
        )

        # Container frame
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(container, orient="vertical", style="Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        
        # Treeview
        self.tree = ttk.Treeview(
            container,
            columns=("id", "tag", "created_at", "records"),
            show="headings",
            style="Custom.Treeview",
            yscrollcommand=scrollbar.set
        )
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Configure columns
        self.tree.heading("id", text="Session System ID", anchor="w")
        self.tree.heading("tag", text="Custom Label Tag", anchor="w")
        self.tree.heading("created_at", text="Created At", anchor="w")
        self.tree.heading("records", text="Records Count", anchor="e")
        
        self.tree.column("id", width=180, anchor="w")
        self.tree.column("tag", width=180, anchor="w")
        self.tree.column("created_at", width=150, anchor="w")
        self.tree.column("records", width=100, anchor="e")
        
        # Bind double-click to load
        self.tree.bind("<Double-1>", lambda event: self._on_double_click())

        # Action Buttons frame at the bottom
        actions_bar = ctk.CTkFrame(self, fg_color="transparent")
        actions_bar.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.grid_rowconfigure(2, weight=0)
        
        # Load Button
        self.btn_load = ctk.CTkButton(
            actions_bar, text="Load Selected Run", height=35, fg_color="#2EA44F",
            hover_color="#227D3B", font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=self._on_load_clicked
        )
        self.btn_load.pack(side="left", padx=(0, 10))
        
        # Rename Button
        self.btn_rename = ctk.CTkButton(
            actions_bar, text="Rename", height=35, fg_color="#2D2D34",
            hover_color="#3A3A42", font=ctk.CTkFont("Segoe UI", 12),
            command=self._on_rename_clicked
        )
        self.btn_rename.pack(side="left", padx=10)
        
        # Delete Button
        self.btn_delete = ctk.CTkButton(
            actions_bar, text="Delete", height=35, fg_color="#D73A49",
            hover_color="#B32431", font=ctk.CTkFont("Segoe UI", 12),
            command=self._on_delete_clicked
        )
        self.btn_delete.pack(side="left", padx=10)

    def refresh_session_list(self):
        # Clear previous rows
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        search_query = self.search_var.get().strip()
        sessions = self.db.get_all_sessions(search_term=search_query if search_query else None)
        
        for s_id, c_name, c_at, count in sessions:
            self.tree.insert(
                "",
                "end",
                iid=s_id,
                values=(s_id, c_name if c_name else "—", c_at, f"{count} items")
            )

    def _get_selected(self):
        """Get the currently selected session from the treeview.
        Returns (session_id, custom_name) or None if nothing is selected.
        """
        selected = self.tree.selection()
        if not selected:
            return None
        session_id = selected[0]
        item_vals = self.tree.item(session_id, "values")
        custom_name = item_vals[1] if item_vals[1] != "—" else ""
        return session_id, custom_name

    def _on_double_click(self):
        result = self._get_selected()
        if result:
            self._action_load(*result)

    def _on_load_clicked(self):
        result = self._get_selected()
        if not result:
            messagebox.showwarning("Selection Required", "Please select a telemetry session to load.", parent=self)
            return
        self._action_load(*result)

    def _on_rename_clicked(self):
        result = self._get_selected()
        if not result:
            messagebox.showwarning("Selection Required", "Please select a session to rename.", parent=self)
            return
        self._action_rename(*result)

    def _on_delete_clicked(self):
        result = self._get_selected()
        if not result:
            messagebox.showwarning("Selection Required", "Please select a session to delete.", parent=self)
            return
        self._action_delete(result[0])

    def _action_load(self, session_id, custom_name):
        label = f"{custom_name} ({session_id})" if custom_name else session_id
        self.load_callback(label)
        self.destroy()

    def _action_rename(self, session_id, current_name):
        new_name = simpledialog.askstring(
            "Assign Custom Tag", f"Provide tracking description alias for:\n{session_id}",
            initialvalue=current_name, parent=self
        )
        if new_name is not None:
            self.db.rename_session(session_id, new_name.strip())
            self.refresh_session_list()
            self.parent._refresh_playback_dropdown()

    def _action_delete(self, session_id):
        confirm = messagebox.askyesno(
            "Purge Confirmation Alert", 
            f"Are you completely sure you want to drop session {session_id}?\nThis action will erase all linked telemetry matrix logs and cannot be undone.",
            parent=self
        )
        if confirm:
            self.db.delete_session(session_id)
            self.refresh_session_list()
            self.parent._refresh_playback_dropdown()
