# 🚀 Quick Start: Gerar Executável e Agendar

## 1️⃣ Pré-requisito: Instalar PyInstaller

```bash
pip install pyinstaller
```

## 2️⃣ Gerar o Executável

Na pasta do projeto, execute:

```bash
build_exe.bat
```

Ou via PowerShell:

```bash
pyinstaller build_exe.spec
```

**Resultado:** `dist\hos_austa_autorizacao_pre.exe`

---

## 3️⃣ Copiar para Local Permanente

```bash
# Crie a pasta de destino
mkdir C:\RPA\hos_austa_autorizacao_pre

# Copie a pasta dist
xcopy dist\* C:\RPA\hos_austa_autorizacao_pre\ /E /I

# Copie o arquivo .env
copy .env C:\RPA\hos_austa_autorizacao_pre\.env
```

---

## 4️⃣ Agendar no Task Scheduler

### Via GUI (Fácil):
1. Abra **Task Scheduler** (`Win + R` → `taskschd.msc`)
2. Crie **Nova Tarefa...**
3. Disparador: Diário às 08:00, repete a cada 5 min
4. Ação: `C:\RPA\hos_austa_autorizacao_pre\hos_austa_autorizacao_pre.exe`
5. Configurações: Executar com privilégios mais altos

### Via PowerShell (Automático):

```powershell
# Execute como Administrator
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00:00 -RepetitionInterval (New-TimeSpan -Minutes 5)
$action = New-ScheduledTaskAction -Execute "C:\RPA\hos_austa_autorizacao_pre\hos_austa_autorizacao_pre.exe" -WorkingDirectory "C:\RPA\hos_austa_autorizacao_pre"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable

Register-ScheduledTask -TaskName "RPA Autorizacoes PA" `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -RunLevel Highest `
    -Description "RPA para autorizar consultas PA - Hospital Austa"
```

---

## 📋 Documentação Completa

Para instruções detalhadas, confiabilidade e troubleshooting, veja: **[AGENDAR.md](AGENDAR.md)**

---

## ✅ Verificar Agendamento

```powershell
# Ver tarefa
Get-ScheduledTask -TaskName "RPA Autorizacoes PA"

# Ver histórico
Get-ScheduledTaskInfo -TaskName "RPA Autorizacoes PA"

# Ver logs
Get-Content C:\RPA\hos_austa_autorizacao_pre\logs\automacao.log -Tail 50
```

---

## ⚠️ Pontos Críticos

- ✅ Coplie o `.env` para a mesma pasta do `.exe`
- ✅ Computador não pode estar em hibernação durante execução
- ✅ Credenciais do Task Scheduler devem ter acesso à rede
- ✅ Oracle Instant Client deve estar instalado (se aplicável)

---

**Pronto! Seu RPA está agendado e rodará automaticamente no Windows.** 🎉
