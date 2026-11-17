# Expoe o Ollama deste notebook Windows via tunel Cloudflare (quick tunnel).
#
# Uso (PowerShell):  .\scripts\tunnel-ollama.ps1
#
# O script:
#   1. garante o Ollama rodando em 127.0.0.1:11434 (inicia `ollama serve` se preciso);
#   2. baixa o cloudflared.exe se nao existir;
#   3. sobe o tunel e mostra a URL publica https://<algo>.trycloudflare.com;
#   4. testa a URL e lista os modelos disponiveis.
#
# Depois, no notebook da aplicacao, ajuste o .env:
#   OLLAMA_BASE_URL=https://<algo>.trycloudflare.com
# e reinicie a aplicacao. A URL muda a cada execucao do script (quick tunnel).
#
# Se o Ollama ja esta rodando (icone na bandeja), o tunel aponta para
# 127.0.0.1 e funciona sem mudar nada. Para acesso tambem pela LAN, defina
# OLLAMA_HOST=0.0.0.0 nas variaveis de ambiente do Windows e reinicie o Ollama.

$ErrorActionPreference = "Stop"
$Port = 11434
$OllamaUrl = "http://127.0.0.1:$Port"

function Test-Ollama {
    try {
        return Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 3
    } catch {
        return $null
    }
}

# 1. Ollama rodando?
$tags = Test-Ollama
$ollamaProc = $null
if (-not $tags) {
    Write-Host "Ollama nao esta rodando; iniciando 'ollama serve'..."
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Error "ollama nao encontrado no PATH. Instale de https://ollama.com e rode de novo."
        exit 1
    }
    $env:OLLAMA_HOST = "0.0.0.0"
    $ollamaProc = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 1
        $tags = Test-Ollama
        if ($tags) { break }
    }
    if (-not $tags) {
        Write-Error "Ollama nao respondeu em 30 s. Verifique 'ollama serve' manualmente."
        exit 1
    }
}
Write-Host "Ollama OK em $OllamaUrl"

# 2. cloudflared.exe
$Cf = Join-Path $PSScriptRoot "cloudflared.exe"
if (-not (Test-Path $Cf)) {
    Write-Host "Baixando cloudflared.exe..."
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $Cf
}

# 3. Tunel
$Log = New-TemporaryFile
$cfProc = Start-Process -FilePath $Cf `
    -ArgumentList "tunnel", "--no-autoupdate", "--url", $OllamaUrl `
    -RedirectStandardError $Log.FullName -PassThru -NoNewWindow

try {
    $Url = $null
    foreach ($i in 1..60) {
        Start-Sleep -Milliseconds 500
        if ($cfProc.HasExited) {
            Get-Content $Log.FullName
            Write-Error "cloudflared encerrou antes de gerar a URL."
            exit 1
        }
        $match = Select-String -Path $Log.FullName -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) {
            $Url = $match.Matches[0].Value
            break
        }
    }
    if (-not $Url) {
        Get-Content $Log.FullName
        Write-Error "Nao foi possivel obter a URL do tunel em 30 s."
        exit 1
    }

    # 4. Teste atraves do tunel
    Write-Host ""
    Write-Host "=============================================================="
    Write-Host " Tunel do Ollama ativo: $Url"
    Write-Host ""
    Write-Host " No notebook da aplicacao, ajuste o .env:"
    Write-Host "   OLLAMA_BASE_URL=$Url"
    Write-Host " e reinicie a aplicacao (ou rode scripts/tunnel-app.sh de novo)."
    Write-Host "=============================================================="
    Write-Host ""

    try {
        $remoteTags = Invoke-RestMethod -Uri "$Url/api/tags" -TimeoutSec 15
        Write-Host "Modelos disponiveis via tunel:"
        foreach ($m in $remoteTags.models) { Write-Host "  - $($m.name)" }
        Write-Host ""
        Write-Host "Confira que OLLAMA_MODEL no .env da aplicacao e um desses nomes."
    } catch {
        Write-Warning "O tunel subiu, mas o teste via URL falhou: $_"
    }

    Write-Host ""
    Write-Host "Ctrl+C encerra o tunel."
    Wait-Process -Id $cfProc.Id
} finally {
    if (-not $cfProc.HasExited) { Stop-Process -Id $cfProc.Id -Force -ErrorAction SilentlyContinue }
    if ($ollamaProc -and -not $ollamaProc.HasExited) {
        Stop-Process -Id $ollamaProc.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $Log.FullName -ErrorAction SilentlyContinue
}