# Graph rendering logic for the telemetry dashboard.
# Handles updating matplotlib plot lines, axis limits, and analytics cards.
# Separated from the main window so the UI code stays clean.

import config
from core.analysis import signal as analytics


class GraphRenderer:
    """Updates the matplotlib chart and analytics metric cards.

    This is the bridge between raw data and what the user sees on screen.
    It reads from the data lists and writes to the matplotlib/tkinter widgets.
    """

    def __init__(self, dashboard_page):
        # The dashboard page has all the matplotlib objects we need:
        # self.page.ax, self.page.canvas, self.page.plot_lines,
        # self.page.toolbar, self.page.cards, self.page.lbl_loss, etc.
        self.page = dashboard_page

    def refresh(self, time_data, channels_data, active_channels,
                normalize_graph, target_channel, expected_pkts, received_pkts):
        """Full dashboard refresh: update graph lines, axes, and analytics cards.

        Called after every new data packet arrives, or when the user toggles
        a setting like channel visibility or normalization.
        """
        # Update the dropped frames and battery indicators
        self.page.lbl_loss.configure(
            text=f"Dropped Frames: {expected_pkts - received_pkts}"
        )
        battery = max(12, 100 - int(expected_pkts / 30))
        self.page.lbl_battery.configure(
            text=f"Battery: {battery}%",
            text_color="#2EA44F" if battery > 25 else "#D73A49",
        )

        if not time_data:
            return

        times = list(time_data)

        # Update each channel's plot line with current data
        for ch in config.AVAILABLE_CHANNELS:
            if not active_channels.get(ch, True):
                continue
            volts = list(channels_data[ch])
            n = min(len(times), len(volts))
            plot_values = volts[:n]
            if normalize_graph:
                plot_values = analytics.normalize(plot_values)
            self.page.plot_lines[ch].set_data(times[:n], plot_values)

        # Auto-scroll the X-axis to follow new data (unless user is panning)
        is_panning = False
        if hasattr(self.page, "toolbar"):
            is_panning = self.page.toolbar.mode.name != "NONE"

        if not is_panning:
            window = config.GRAPH_DISPLAY_WINDOW_SEC
            latest = times[-1]
            if latest > window:
                self.page.ax.set_xlim(latest - window, latest)
            else:
                self.page.ax.set_xlim(0, window)

        # Set Y-axis limits based on normalization mode
        if normalize_graph:
            self.page.ax.set_ylim(0.0, 1.0)
        else:
            self._auto_scale_y(channels_data, active_channels)

        self.page.canvas.draw_idle()

        # Update the analytics metric cards
        self._update_cards(times, channels_data, target_channel)

    def update_visibility(self, time_data, channels_data, active_channels, normalize_graph):
        """Called when the user toggles a channel's visibility checkbox.

        Re-populates the line data for visible channels and hides invisible ones.
        """
        times = list(time_data) if time_data else []

        for ch in config.AVAILABLE_CHANNELS:
            is_visible = active_channels.get(ch, True)

            if is_visible and times:
                volts = list(channels_data[ch])
                n = min(len(times), len(volts))
                plot_values = volts[:n]
                if normalize_graph:
                    plot_values = analytics.normalize(plot_values)
                self.page.plot_lines[ch].set_data(times[:n], plot_values)

            self.page.plot_lines[ch].set_visible(is_visible)

        self.page.ax.relim()
        self.page.ax.autoscale_view(scalex=False, scaley=True)
        self.page.canvas.draw_idle()

    def _auto_scale_y(self, channels_data, active_channels):
        """Calculate Y-axis bounds from the visible channel data with 5% padding."""
        y_min, y_max = None, None
        for ch in config.AVAILABLE_CHANNELS:
            if not active_channels.get(ch, True):
                continue
            values = list(channels_data[ch])
            if not values:
                continue
            ch_min, ch_max = min(values), max(values)
            y_min = ch_min if y_min is None else min(y_min, ch_min)
            y_max = ch_max if y_max is None else max(y_max, ch_max)

        if y_min is not None and y_max is not None:
            padding = 0.1 if y_min == y_max else (y_max - y_min) * 0.05
            self.page.ax.set_ylim(y_min - padding, y_max + padding)

    def _update_cards(self, times, channels_data, target_channel):
        """Compute and display analytics for the selected target channel."""
        v_data = list(channels_data[target_channel])
        if not v_data:
            return

        cards = self.page.cards

        # Peak-to-peak voltage
        pp = analytics.peak_to_peak(v_data)
        cards["Peak-to-Peak"]["value"].configure(text=f"{pp:.2f} V")

        # Signal frequency estimate
        freq = analytics.estimate_frequency(times, v_data)
        if freq is not None:
            cards["Frequency"]["value"].configure(text=f"{freq:.1f} Hz")
        else:
            cards["Frequency"]["value"].configure(text="--")

        # Time at which peak voltage occurred
        pt = analytics.find_peak_time(times, v_data)
        cards["Peak Time"]["value"].configure(text=f"{pt:.2f} s")

        # Rise time (10% to 90% of range)
        rt = analytics.rise_time(times, v_data)
        if rt is not None:
            cards["Rise Time"]["value"].configure(text=f"{rt:.2f} s")
        else:
            cards["Rise Time"]["value"].configure(text="--")

        # Maximum inter-channel jitter
        jitter = analytics.max_jitter(
            times, channels_data, target_channel, config.AVAILABLE_CHANNELS
        )
        cards["Max Jitter (Δt)"]["value"].configure(
            text=f"{jitter:.1f} ms" if jitter > 0 else "0.0 ms"
        )
