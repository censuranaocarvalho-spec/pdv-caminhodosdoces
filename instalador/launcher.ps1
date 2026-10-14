$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:Raiz = $env:PDV_RAIZ
$script:Bat = $env:PDV_BAT
$script:Python = Join-Path $script:Raiz "core-orders\venv\Scripts\python.exe"
$script:Main = Join-Path $script:Raiz "main.py"
$script:Url = "http://127.0.0.1:8090/"

function Get-Pdv {
  if (-not (Test-Path -LiteralPath $script:Python)) { return @() }
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ExecutablePath -and ($_.ExecutablePath -ieq $script:Python)
  })
}

function Set-Atalho {
  try {
    $mesa = [Environment]::GetFolderPath("Desktop")
    $atalho = Join-Path $mesa "Caminho dos Doces.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($atalho)
    $link.TargetPath = $script:Bat
    $link.WorkingDirectory = $script:Raiz
    $link.Description = "Ligar e desligar o PDV"
    $link.Save()
  } catch {}
}

function Wait-Pagina {
  for ($i = 0; $i -lt 25; $i++) {
    try {
      $pedido = [System.Net.HttpWebRequest]::Create($script:Url)
      $pedido.Timeout = 800
      $pedido.Method = "GET"
      $resposta = $pedido.GetResponse()
      $resposta.Close()
      return $true
    } catch {
      Start-Sleep -Milliseconds 400
    }
  }
  return $false
}

function Set-Barra {
  try {
    $mesa = [Environment]::GetFolderPath("Desktop")
    $nome = "Caminho dos Doces.lnk"
    $atalho = Join-Path $mesa $nome
    if (-not (Test-Path -LiteralPath $atalho)) { return $false }
    $shell = New-Object -ComObject Shell.Application
    $pasta = $shell.Namespace($mesa)
    $item = $pasta.ParseName($nome)
    if (-not $item) { return $false }
    foreach ($verbo in @($item.Verbs())) {
      $texto = (($verbo.Name + "") -replace "&", "").Trim()
      if ($texto -match "Desafixar|Unpin") { return $true }
      if ($texto -match "Fixar na barra de tarefas|Pin to taskbar") {
        $verbo.DoIt()
        return $true
      }
    }
  } catch {}
  return $false
}

function Update-Loja {
  try {
    if (-not (Test-Path -LiteralPath (Join-Path $script:Raiz ".git"))) { return $false }
    $git = $null
    $comando = Get-Command git -ErrorAction SilentlyContinue
    if ($comando) { $git = $comando.Source }
    $padrao = Join-Path $env:ProgramFiles "Git\cmd\git.exe"
    if (-not $git -and (Test-Path -LiteralPath $padrao)) { $git = $padrao }
    if (-not $git) { return $false }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $git
    $info.Arguments = '-C "' + $script:Raiz + '" pull --ff-only origin main'
    $info.WorkingDirectory = $script:Raiz
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($info)
    $saidaTask = $proc.StandardOutput.ReadToEndAsync()
    $erroTask = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit(60000)) {
      try { $proc.Kill() } catch {}
      return $false
    }
    $texto = ($saidaTask.Result + " " + $erroTask.Result)
    if ($proc.ExitCode -ne 0) { return $false }
    return ($texto -match "Fast-forward|file changed|files changed|inserc|Atualizando")
  } catch {
    return $false
  }
}

Set-Atalho
$script:NaBarra = Set-Barra

$form = New-Object System.Windows.Forms.Form
$form.Text = "Caminho dos Doces"
$form.ClientSize = New-Object System.Drawing.Size(420, 300)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(255, 248, 245)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 12)

$titulo = New-Object System.Windows.Forms.Label
$titulo.Text = "Caminho dos Doces"
$titulo.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$titulo.ForeColor = [System.Drawing.Color]::FromArgb(124, 74, 58)
$titulo.TextAlign = "MiddleCenter"
$titulo.SetBounds(16, 12, 388, 40)

$nota = New-Object System.Windows.Forms.Label
if ($script:NaBarra) {
  $nota.Text = "Abre e fecha o programa. O caixa nao muda."
} else {
  $nota.Text = "Clique direito no icone e escolha Fixar na barra de tarefas."
}
$nota.ForeColor = [System.Drawing.Color]::FromArgb(124, 74, 58)
$nota.TextAlign = "MiddleCenter"
$nota.SetBounds(16, 50, 388, 36)

$ligar = New-Object System.Windows.Forms.Button
$ligar.Text = "Ligar"
$ligar.SetBounds(36, 92, 348, 62)
$ligar.FlatStyle = "Flat"
$ligar.BackColor = [System.Drawing.Color]::FromArgb(124, 74, 58)
$ligar.ForeColor = [System.Drawing.Color]::White
$ligar.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)

$desligar = New-Object System.Windows.Forms.Button
$desligar.Text = "Desligar"
$desligar.SetBounds(36, 166, 348, 62)
$desligar.FlatStyle = "Flat"
$desligar.BackColor = [System.Drawing.Color]::FromArgb(194, 229, 233)
$desligar.ForeColor = [System.Drawing.Color]::FromArgb(124, 74, 58)
$desligar.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)

$status = New-Object System.Windows.Forms.Label
$status.TextAlign = "MiddleCenter"
$status.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$status.SetBounds(16, 244, 388, 36)

function Update-Status {
  if (@(Get-Pdv).Count -gt 0) {
    $status.Text = "O PDV esta ligado"
    $status.ForeColor = [System.Drawing.Color]::FromArgb(22, 101, 52)
  } else {
    $status.Text = "O PDV esta desligado"
    $status.ForeColor = [System.Drawing.Color]::FromArgb(124, 74, 58)
  }
}

$ligar.Add_Click({
  $ligar.Enabled = $false
  $desligar.Enabled = $false
  try {
    if (-not (Test-Path -LiteralPath $script:Python)) {
      [System.Windows.Forms.MessageBox]::Show("Primeiro de dois cliques em instalar.bat", "Caminho dos Doces")
      return
    }
    $status.Text = "Atualizando..."
    $form.Refresh()
    $script:Baixou = Update-Loja
    if (@(Get-Pdv).Count -eq 0) {
      $status.Text = "Ligando..."
      $form.Refresh()
      $info = New-Object System.Diagnostics.ProcessStartInfo
      $info.FileName = $script:Python
      $info.Arguments = '"' + $script:Main + '"'
      $info.WorkingDirectory = $script:Raiz
      $info.UseShellExecute = $false
      $info.CreateNoWindow = $true
      [void][System.Diagnostics.Process]::Start($info)
      if (-not (Wait-Pagina)) {
        [System.Windows.Forms.MessageBox]::Show("O PDV nao abriu. Use iniciar.bat para ver a mensagem.", "Caminho dos Doces")
        return
      }
    }
    $quando = [DateTimeOffset]::Now.ToUnixTimeSeconds()
    Start-Process ($script:Url + "?v=" + $quando)
  } finally {
    $ligar.Enabled = $true
    $desligar.Enabled = $true
    Update-Status
    if ($script:Baixou) { $status.Text = "Atualizado. Se a frase antiga continuar, aperte F5." }
  }
})

$desligar.Add_Click({
  $ligar.Enabled = $false
  $desligar.Enabled = $false
  try {
    foreach ($proc in @(Get-Pdv)) {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 400
  } finally {
    $ligar.Enabled = $true
    $desligar.Enabled = $true
    Update-Status
  }
})

$form.Controls.AddRange(@($titulo, $nota, $ligar, $desligar, $status))
Update-Status
[void]$form.ShowDialog()
