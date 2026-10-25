# Restarts Lavalink and the Discord bot, Lavalink first so the bot has
# something to reconnect to. Also what starts the stack after a login: the
# Startup folder holds Run_AlterBard.bat, which calls this script.
#
# Originally meant to be scheduled nightly: on 2026-08-12 the youtube
# plugin started failing every track with "This video requires login" and
# stayed broken for ~20h until Lavalink was restarted by hand - a clean
# restart before that state can build up is cheaper than manual recovery.
#
# Processes are matched by command line, not by a remembered PID - PIDs are
# reused by whatever process starts next, and this machine runs several other
# bots (HorusBot, Twitch_Bot_V2, AlterMMO-Bot-RPG) that must not be touched.

$repoRoot = "C:\Programowanie\AlterBard"
$logFile = Join-Path $repoRoot "logs\restart_music_stack.log"

function Write-Log($message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "$timestamp $message"
}

Write-Log "Restart starting."

# --- Lavalink ---
$lavalink = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
    Where-Object { $_.CommandLine -like '*Lavalink.jar*' }

foreach ($proc in $lavalink) {
    Write-Log "Stopping Lavalink PID $($proc.ProcessId)."
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 5

Start-Process -FilePath "java" -ArgumentList "-jar Lavalink.jar" `
    -WorkingDirectory $repoRoot -WindowStyle Hidden
Write-Log "Lavalink relaunched."

# Give Lavalink time to load its plugins and open its websocket - a cold
# start takes longer than the gap between two log lines suggests.
Start-Sleep -Seconds 30

# --- Discord bot ---
$bot = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*AlterBard*init.py*' }

foreach ($proc in $bot) {
    Write-Log "Stopping bot PID $($proc.ProcessId)."
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 3

# The venv's python by full path, for two reasons. "activate.bat && init.py"
# went through the .py file association, which picked a global Python without
# the bot's packages - the bot died before it could log a line (2026-10-25).
# And the full script path puts "AlterBard" into the command line, which is
# what the stop step above matches on.
Start-Process -FilePath (Join-Path $repoRoot ".venv\Scripts\python.exe") `
    -ArgumentList ('"' + (Join-Path $repoRoot "init.py") + '"') `
    -WorkingDirectory $repoRoot -WindowStyle Hidden
Write-Log "Bot relaunched."

Write-Log "Restart finished."
