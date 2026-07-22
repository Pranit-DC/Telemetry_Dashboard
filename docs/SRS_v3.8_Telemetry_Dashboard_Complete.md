# Software Requirement Specification (SRS)

# Telemetry Dashboard

**Version:** 3.8  
**Project Type:** BARC Training Project  
**Platform:** Windows Desktop Application  
**Language:** Python 3.x

---

# 1. Introduction

## 1.1 Purpose

This document defines the software requirements for Version 3.8 of the Telemetry Dashboard. It describes the functionality, constraints, interfaces, and overall behavior of the system.

The dashboard is developed as a training project to understand software development practices and telemetry visualization. The current version supports simulation-based telemetry acquisition and provides features for data visualization, storage, logging, session management, and configuration. Future versions will integrate real telemetry hardware.

---

## 1.2 Scope

The Telemetry Dashboard is a desktop application developed using Python. It is designed to visualize voltage data against elapsed time in real time.

The current version provides:

- Live telemetry visualization
- Multi-channel graph plotting
- Telemetry metrics
- Session management
- Historical playback
- SQLite database storage
- Logging subsystem
- Graph configuration
- Settings management
- Graph normalization
- Automatic Y-axis scaling

The project is currently based on simulated telemetry data. Hardware communication through BLE and Arduino GIGA will be added in future versions.

---

## 1.3 Product Overview

The Telemetry Dashboard provides an easy-to-use graphical interface for monitoring telemetry data.

The application continuously receives simulated voltage samples, displays them on a real-time graph, calculates useful telemetry metrics, stores acquisition data inside an SQLite database, maintains application logs, and allows users to manage historical sessions.

The software is designed with a modular architecture so future hardware integration and additional analytics can be added without major architectural changes.

---

# 2. General Description

## 2.1 Product Perspective

The Telemetry Dashboard is a standalone desktop application developed using Python. It follows a modular architecture where different functionalities such as data acquisition, visualization, storage, logging, and configuration are separated into independent modules.

The current version uses simulated telemetry data for development and testing. The architecture is designed so that the simulation module can later be replaced by real BLE communication with minimal changes to the remaining software.

---

## 2.2 Product Features

The current version of the dashboard provides the following features:

- Real-time telemetry simulation
- Start, Stop and Pause acquisition
- Single and multi-channel telemetry visualization
- Live voltage vs elapsed time graph
- Telemetry metrics (Vpp, ΔT, Rise Time, Peak Time, Target Frequency)
- Graph normalization
- Automatic Y-axis scaling
- Matplotlib navigation toolbar
- SQLite database storage
- Historical session playback
- Session management
- Settings window
- Graph configuration
- Logging and diagnostics
- CSV data export

The following features are planned but are not implemented in the current version:

- Analytics window
- Report generation
- BLE communication
- Arduino GIGA integration
- Live hardware telemetry acquisition

---

## 2.3 User Characteristics

The application is intended for users who need to visualize and monitor telemetry data.

The user is expected to have:

- Basic computer knowledge
- Basic understanding of telemetry data
- No programming knowledge is required to operate the dashboard

---

## 2.4 Operating Environment

The application is designed to run in the following environment:

### Hardware

- Windows/Linux PC
- Standard display
- Mouse and keyboard

### Software

- Windows 10 or Windows 11 or Linux
- Python 3.x
- CustomTkinter
- Matplotlib
- SQLite
- NumPy

The software is designed to operate in an offline (air-gapped) environment.

---

## 2.5 Assumptions and Dependencies

### Assumptions

- Telemetry data is currently simulated.
- The system assumes valid input data.
- SQLite database is available for local storage.
- Required Python packages are already installed.

### Dependencies

- Python 3.x
- CustomTkinter
- Matplotlib
- SQLite
- NumPy

Future versions will additionally depend on:

- Arduino GIGA
- BLE communication module
- PIN-6D photodiode hardware

---