# SoE SSL/TLS Configuration Guide (`--sec`)

This document provides a comprehensive manual on how to secure your **Serial over Ethernet (SoE)** connections using custom SSL/TLS certificates.

While the `--secauto` option is convenient for quick tests (generating temporary self-signed certificates in memory), the `--sec` option allows for a robust, production-grade setup using persistent certificates and keys.

---

## 1. Overview: Why use `--sec`?

The `--sec CERT,KEY` option allows you to provide specific cryptographic files to the SoE application.

*   **Persistence:** Your keys remain the same across restarts.
*   **Encryption:** All traffic between the Server and Client/Bridge is encrypted using AES (or the best available cipher).
*   **Privacy:** Prevents eavesdropping on the serial data stream.
*   **Format:** The application expects **PEM-encoded** X.509 certificates and RSA private keys.

---

## 2. Prerequisites

To generate valid certificates, you need the **OpenSSL** toolkit.

*   **Linux:** Usually pre-installed. If not: `sudo apt install openssl` (Debian/Ubuntu) or `sudo yum install openssl` (RHEL/CentOS).
*   **Windows:** We strongly recommend installing **Git for Windows** (which includes "Git Bash"), as it provides the standard `openssl` command line tool. Alternatively, you can install Win64OpenSSL.

---

## 3. Generating Certificates on Linux

Open your terminal and follow these steps.

### Method A: The Quick One-Liner (Self-Signed)
This creates a certificate and key in a single step. Ideally suited for direct Server-Client links.

1.  Run the command:
    ```bash
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes
    ```
2.  **Fill in the prompts:**
    *   **Country Name:** (e.g., US, PL)
    *   **Common Name (CN):** **Crucial.** Enter the IP address or Hostname of the server (e.g., `192.168.1.50` or `myserialserver`).
    *   Other fields can be left blank or filled as desired.

3.  **Result:** You now have `cert.pem` (Public Certificate) and `key.pem` (Private Key).

### Method B: Production Approach (Separate Key and CSR)
Use this if you need to submit a request to an internal CA, but for this manual, we will self-sign it.

1.  **Generate Private Key:**
    ```bash
    openssl genrsa -out soe_private.key 4096
    ```
2.  **Generate Signing Request (CSR):**
    ```bash
    openssl req -new -key soe_private.key -out soe_request.csr
    ```
3.  **Generate Certificate:**
    ```bash
    openssl x509 -req -days 365 -in soe_request.csr -signkey soe_private.key -out soe_cert.crt
    ```

---

## 4. Generating Certificates on Windows

### Method A: Using Git Bash (Recommended)
This is identical to the Linux method and is the least error-prone way to get PEM files on Windows.

1.  Open **Git Bash**.
2.  Navigate to your SoE folder:
    ```bash
    cd /c/soft_common/skrypty/serial_OK/
    ```
3.  Run the OpenSSL command:
    ```bash
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes
    ```
4.  Answer the prompts (Common Name is important, see Linux section).

### Method B: Using PowerShell (Native)
If you cannot install OpenSSL/Git Bash, you can use PowerShell, but it requires extra steps to export to the `.pem` format Python requires.

1.  **Generate the Certificate in Windows Store:**
    Run this command in PowerShell (Admin):
    ```powershell
    $cert = New-SelfSignedCertificate -DnsName "192.168.1.50" -CertStoreLocation "cert:\LocalMachine\My"
    ```

2.  **Export the Certificate (Public Key):**
    ```powershell
    $destCert = "C:\Path\To\cert.pem"
    $certContent = "-----BEGIN CERTIFICATE-----`r`n" + [Convert]::ToBase64String($cert.RawData, "InsertLineBreaks") + "`r`n-----END CERTIFICATE-----"
    [IO.File]::WriteAllText($destCert, $certContent)
    ```

3.  **Export the Private Key (Complex):**
    Windows natively exports keys as `.pfx`. Python needs `.pem`.
    *   You must export the PFX from the Certificate Manager (`certlm.msc`).
    *   Then you **must** use a tool like OpenSSL to convert the PFX to PEM.
    *   *Conclusion:* **Method A (Git Bash) is significantly better for this use case.**

---

## 5. Configuring SoE Components

The `--sec` argument requires **two file paths** separated by a **comma**, with **no spaces**.

**Syntax:**
```bash
--sec PATH_TO_CERT,PATH_TO_KEY
```

**Important:** You **must** also provide a password (`--pwd`) when using security modes. This adds an extra layer of authorization.

### 1. Configuring the SoE Server
The Server uses the certificate to prove its identity and encrypt the stream.

**Linux Example:**
```bash
python3 serial_server.py \
  --port 10001 \
  --pwd mysecretpassword \
  --sec /etc/ssl/certs/cert.pem,/etc/ssl/private/key.pem
```

**Windows Example:**
```cmd
python serial_server.py ^
  --port 10001 ^
  --pwd mysecretpassword ^
  --sec C:\Keys\cert.pem,C:\Keys\key.pem
```

### 2. Configuring the SoE Client / Bridge
The Client/Bridge also supports loading certificates. In `0.0.x` versions of SoE, if you use `--sec` on the client, it loads these certificates to present them to the server (Mutual TLS) or simply to initialize the SSL context correctly.

**Client Example:**
```bash
python serial_client.py \
  -H 192.168.1.50 -p 10001 \
  --pwd mysecretpassword \
  --sec cert.pem,key.pem
```

**Bridge Example:**
```bash
python serial_bridge.py \
  -H 192.168.1.50 -p 10001 \
  --namedpipe MyPipe \
  --pwd mysecretpassword \
  --sec cert.pem,key.pem
```

---

## 6. Using Configuration Files (`.conf`)

Instead of typing paths every time, put them in your config file.

**soeserver.conf:**
```ini
[DEFAULT]
port = 10001
pwd = securepassword
# Note: Use full absolute paths to avoid "File not found" errors
sec = c:\soft_common\certs\cert.pem,c:\soft_common\certs\key.pem
```

**soeclient.conf:**
```ini
host = 192.168.1.50
port = 10001
pwd = securepassword
sec = /home/user/certs/cert.pem,/home/user/certs/key.pem
```

---

## 7. Troubleshooting

### Error: `FileNotFoundError` or `SSL Load Failure`
*   **Cause:** Python cannot find the files specified.
*   **Fix:** Ensure you are using **Absolute Paths** (e.g., `C:\Keys\cert.pem` instead of `cert.pem`).
*   **Fix:** Ensure there are no spaces around the comma in the argument (Correct: `file1,file2`. Incorrect: `file1, file2`).

### Error: `SSL Handshake Failed`
*   **Cause:** Mismatch between Server and Client SSL modes.
*   **Fix:** Ensure **BOTH** sides are running with security enabled (`--sec` or `--secauto`). You cannot connect a RAW client to an SSL Server.
*   **Cause:** System clock skew.
*   **Fix:** Ensure both computers have the correct time/date.

### Error: `Password Required`
*   **Cause:** You used `--sec` but forgot `--pwd`.
*   **Fix:** The architecture requires a password for authorization when SSL is enabled. Add `--pwd YOURPASS`.
