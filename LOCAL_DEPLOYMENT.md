# 🌐 FDRE Mesob Center Inventory Management System - Local Deployment Guide
This guide provides step-by-step instructions to configure, run, and allow multi-user access to your Odoo Inventory application from any computer, tablet, or smartphone connected to your local office network (Wi-Fi or LAN).

---

## 📋 System Setup Information
*   **Active Git Branch:** `develop` (Fully synchronized with GitHub PR merges for all UI designs, Odoo 19 bug fixes, and unit tests)
*   **Active Database:** `GraceDB`
*   **Server LAN IP Address:** `172.16.63.234`
*   **Standard Connection Port:** `8069`

---

## 🔌 Step 1: Run the Server on the `develop` Branch
Before starting, ensure that your command console is running Odoo on the correct Git branch:
1.  Open your project directory in terminal.
2.  Ensure you are on the clean `develop` branch:
    ```powershell
    git checkout develop
    ```
3.  Execute your local startup script:
    ```powershell
    .\start_odoo.bat
    ```
This runs the Odoo server using your freshly audited, modern Python models and beautiful UI layouts.

---

## 🛡️ Step 2: Open Odoo Port in Windows Firewall (Required)
By default, Windows Firewall blocks incoming network traffic on port `8069`. To allow other devices on your Wi-Fi/LAN to access the application, run this simple command on the host server computer:

1.  Right-click your Windows **Start Button** and select **PowerShell (Admin)** or **Command Prompt (Admin)**.
2.  Copy and run this exact command to add an inbound firewall rule:
    ```powershell
    New-NetFirewallRule -DisplayName "Odoo Port 8069" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8069
    ```

---

## ⚙️ Step 3: Configure Odoo for Network Binding
To ensure Odoo listens to connections from your local network instead of restricting access to `localhost` (127.0.0.1) only:
1.  Open your Odoo configuration file at:
    `C:\Program Files\Odoo 19.0.20260218\server\odoo.conf`
2.  Search for `http_interface` or `xmlrpc_interface`.
3.  Ensure the interface is set to bind to all addresses (`0.0.0.0`) or is commented out with a semicolon (`;`):
    ```ini
    http_interface = 0.0.0.0
    ```
4.  Restart the Odoo Service to apply changes:
    *   Open Windows **Services** (`services.msc`).
    *   Find **Odoo Server 19.0** and click **Restart**.

---

## 📱 Step 4: Access Odoo from Other Devices
Now, any device connected to the same Wi-Fi/LAN can immediately connect to your system. Simply open any web browser (on a laptop, phone, or tablet) and enter your server's LAN URL:

👉 **`http://172.16.63.234:8069`**

### Logins for Team Testing:
Your database **`GraceDB`** contains the following newly audited test users:
*   **Storekeeper:** `sk_auditor` / `sk_auditor@mesob.com`
*   **PAO Supervisor:** `pao_super` / `pao@mesob.com`
*   **Security Guard:** `sk_in` / `sk2@mesob.com`
*   **Witness Auditor:** `witness_aud` / `witness@mesob.com`
