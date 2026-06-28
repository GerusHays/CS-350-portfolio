# CS 350 – Smart Thermostat Prototype

## Overview

This repository contains my final project for CS 350: Emerging Systems Architectures and Technologies. The project demonstrates the design and implementation of a prototype smart thermostat using a Raspberry Pi and Python. The thermostat integrates multiple hardware peripherals, including an AHT20 temperature sensor, LCD display, push buttons, LEDs, and UART communication, to simulate the operation of a smart thermostat capable of monitoring temperature, responding to user input, and transmitting system status.

---

## Project Summary

The objective of this project was to develop an embedded application capable of monitoring room temperature and controlling heating and cooling states through a state machine. The thermostat continuously reads temperature data from an AHT20 sensor over I2C, allows the user to adjust the desired temperature using push buttons, displays current system information on an LCD, and reports system status over UART every 30 seconds to simulate communication with a remote server.

The application uses three operating modes:

- **Off**
- **Heating**
- **Cooling**

The mode button cycles through each state while additional buttons increase or decrease the temperature set point. LEDs provide visual indication of heating or cooling activity based on the current room temperature and selected set point.

---

## What I Did Well

One of the biggest strengths of this project was successfully integrating several hardware interfaces into a single application while keeping the software organized and modular. I used a state machine to manage the thermostat's behavior, making the code easier to understand and maintain. Separating functionality into individual methods for sensor readings, display updates, LED control, and UART communication also made troubleshooting and future improvements much easier.

---

## Where I Could Improve

If I were to continue developing this project, I would improve the error handling for hardware failures and communication errors. I would also add additional thermostat functionality such as programmable schedules, hysteresis to reduce unnecessary heating and cooling cycles, Wi-Fi connectivity, and cloud-based monitoring. Testing the application on physical hardware for a longer period would also help validate long-term reliability.

---

## Tools and Resources

Throughout this project I expanded my experience using:

- Python
- Raspberry Pi
- GPIO
- I2C communication
- UART communication
- State machine design
- Embedded systems programming
- Hardware datasheets and documentation
- Modular software development practices

These resources will continue to support future embedded systems and software engineering projects.

---

## Transferable Skills

This project strengthened several skills that directly apply to future coursework and professional software engineering projects, including:

- Embedded software development
- Hardware and software integration
- State machine implementation
- GPIO, I2C, and UART communication
- Modular software architecture
- Debugging hardware/software interactions
- Evaluating embedded hardware platforms based on system requirements

These skills are applicable to embedded systems, robotics, IoT devices, and unmanned aircraft systems.

---

## Maintainability, Readability, and Adaptability

The software was written using modular design principles with clearly separated responsibilities for each hardware component. Constants were used instead of hard-coded values to simplify future configuration changes. The state machine architecture keeps the program organized and allows additional operating modes or hardware features to be added without major changes to the overall structure.

This design makes the project easier to read, maintain, debug, and expand as additional functionality is introduced.

---

## Repository Contents

- `Thermostat.py` – Main Python application implementing the smart thermostat
- `Project State Machine.pdf` – State machine diagram illustrating thermostat operation
- `CS 350 Final Project Report.docx` – Final project report describing the system architecture, hardware evaluation, and design decisions
