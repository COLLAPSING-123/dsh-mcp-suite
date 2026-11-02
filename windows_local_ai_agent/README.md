# Windows Local AI Agent

Windows-hosted Python agent using an OpenAI-compatible Chat Completions API. It can execute approved commands in Windows, WSL Ubuntu, and an Ubuntu VM over SSH, and operate the visible Windows desktop using PyAutoGUI. To control Ubuntu's GUI, bring its VMware Workstation window to the foreground first.

## Important
- Every command, screenshot, and desktop action requires local approval.
- The command deny-list is only a guardrail, not a sandbox. Run as a normal non-admin user and use VM snapshots.
- Screenshots are sent to your configured API endpoint. Do not capture sensitive screens unless permitted.
- The provider must support OpenAI-compatible Chat Completions tool calls. Screenshot reasoning also requires image input support.
- GUI control is through the visible Windows display; it does not directly control a hidden VM framebuffer.

## Install
Open non-administrator PowerShell in this folder:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
Copy-Item .env.example .env
notepad .env
```
Configure `BASE_URL`, `API_KEY`, `MODEL`, `WSL_DISTRO`, `VM_HOST`, `VM_USER`, and optionally `SSH_KEY_PATH`.

## Connect the Ubuntu VM
Inside VM:
```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
ip addr
```
On Windows:
```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\ai_agent_vm"
```
Install the public key in the VM user's `~/.ssh/authorized_keys`. Test SSH and verify host key:
```powershell
ssh -i "$HOME\.ssh\ai_agent_vm" labuser@192.168.1.50 "uname -a"
```
Use your actual username and reachable VM IP. VMware NAT/bridged settings affect connectivity.

## Run
```powershell
.\.venv\Scripts\Activate.ps1
python -m agent.main
```
Try: `Check WSL kernel version`, `Check VM disk space`, or `Take a screenshot of the current desktop and describe it`.
Type `/exit` to quit.

## Tests
```powershell
python -m unittest discover -s tests -v
```

## Provider compatibility
`BASE_URL` is typically the provider's OpenAI-compatible base URL ending in `/v1`. `MODEL` must be the exact model ID and support function calling. Some providers do not support vision messages; screenshot analysis will fail on those endpoints. The project uses Chat Completions, not Responses API.

## Security notes
Use a standard account, a dedicated workspace, SSH keys, verified host keys, and VM snapshots. Avoid running the agent elevated. A deny-list cannot make arbitrary shell commands safe. Audit records are written to `logs/audit.jsonl`; secrets and screenshot image bytes are not logged.
