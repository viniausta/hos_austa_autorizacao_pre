# 🚀 Guia: Agendar RPA no Windows Task Scheduler

Este documento orienta como compilar o projeto em um executável (.exe) e agendá-lo no **Agendador de Tarefas do Windows**.

---

## 📋 Pré-requisitos

- ✅ Python 3.10+ instalado
- ✅ Projeto `hos_austa_autorizacao_pre` configurado localmente
- ✅ Arquivo `.env` criado com todas as variáveis de ambiente
- ✅ Acesso ao Agendador de Tarefas do Windows (Admin)

---

## 🔨 PASSO 1: Instalar PyInstaller

```powershell
pip install pyinstaller
```

---

## 🏗️ PASSO 2: Gerar o Executável

### Opção A: Via Script Batch (Recomendado)

1. Abra **PowerShell** ou **CMD** na pasta do projeto
2. Execute:

```bash
cd c:\ProjetosPython\DEV\hos_austa_autorizacao_pre
build_exe.bat
```

3. Aguarde o build terminar (~2-5 min, depende do PC)
4. Sucesso! O arquivo estará em: `dist\hos_austa_autorizacao_pre.exe`

### Opção B: Via PyInstaller Direto

```bash
cd c:\ProjetosPython\DEV\hos_austa_autorizacao_pre
pyinstaller build_exe.spec
```

---

## 📁 PASSO 3: Organizar os Arquivos

Após o build, copie a pasta `dist` para um local permanente (sugestão: `C:\RPA\hos_austa_autorizacao_pre\`):

```
C:\RPA\hos_austa_autorizacao_pre\
├── hos_austa_autorizacao_pre.exe      ← Executável Principal
├── .env                                ← Arquivo de configuração (COPIAR AQUI!)
├── _internal/                          ← Dependências (auto-gerado)
│   ├── selenium/
│   ├── oracledb/
│   ├── requests/
│   └── ...
└── logs/                               ← Será criado automaticamente
```

**IMPORTANTE:** Copie o arquivo `.env` para a mesma pasta do `.exe`!

```bash
copy c:\ProjetosPython\DEV\hos_austa_autorizacao_pre\.env C:\RPA\hos_austa_autorizacao_pre\.env
```

---

## ⏰ PASSO 4: Agendar no Windows Task Scheduler

### Método 1: Via GUI (Interface Gráfica)

1. **Abra o Agendador de Tarefas:**
   - Pressione `Win + R`
   - Digite: `taskschd.msc`
   - Pressione `Enter`

2. **Crie uma nova tarefa:**
   - Clique em **Criar Tarefa...** (painel direito)
   - Guia **Geral:**
     - Nome: `RPA Autorizacoes PA`
     - Descrição: `Robô RPA para autorizar consultas PA - Hospital Austa`
     - ☑ Executar com privilégios mais altos
     - ☑ Usar a melhor Segurança do Windows NT AUTHORITY

3. **Guia Disparadores:**
   - Clique **Novo...** e escolha:
     - **Tipo:** Segundo uma agenda
     - **Frequência:** Diária / Semanal / Horária (conforme necessário)
     - **Hora de início:** Ex: 08:00:00
     - **Repetir tarefa a cada:** 5 minutos (ou conforme desejado)
     - ☑ Ativar para que o Windows execute se a tarefa não foi concluída à sua hora

4. **Guia Ações:**
   - Clique **Novo...:**
     - **Ação:** Iniciar um programa
     - **Programa/script:** `C:\RPA\hos_austa_autorizacao_pre\hos_austa_autorizacao_pre.exe`
     - **Iniciar em (opcional):** `C:\RPA\hos_austa_autorizacao_pre`

5. **Guia Condições:**
   - ☑ Iniciar a tarefa apenas se o computador estiver em uma rede específica
   - ☑ Acordar o computador para executar esta tarefa (se quiser)

6. **Guia Configurações:**
   - ☑ Se a tarefa falhar: reintentar cada 5 minutos (até 3 vezes)
   - ☑ Parar a tarefa se ela é executada por mais de: 4 horas (ou conforme necessário)

7. Clique **OK** e insira suas credenciais do Windows

---

### Método 2: Via PowerShell Script

Crie um arquivo `agendar_rpa.ps1`:

```powershell
# Script para agendar RPA no Task Scheduler
# Execute como Administrator

$taskName = "RPA Autorizacoes PA"
$exePath = "C:\RPA\hos_austa_autorizacao_pre\hos_austa_autorizacao_pre.exe"
$workDir = "C:\RPA\hos_austa_autorizacao_pre"

# Define disparador: Diário às 8h, repete a cada 5 minutos
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00:00 -RepetitionInterval (New-TimeSpan -Minutes 5)

# Define ação: Executar o .exe
$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $workDir

# Define configurações
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable

# Registra a tarefa
Register-ScheduledTask -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Robô RPA para autorizar consultas PA - Hospital Austa"

Write-Host "✓ Tarefa '$taskName' agendada com sucesso!"
```

Execute como Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\agendar_rpa.ps1
```

---

## ✅ Verificar Agendamento

1. **No Task Scheduler:**
   - Procure por `RPA Autorizacoes PA` na lista
   - Clique em **Histórico** para ver execuções anteriores

2. **Ver logs:**
   - Abra `C:\RPA\hos_austa_autorizacao_pre\logs\automacao.log`
   - Ou `automacao.log.<data>` para datas específicas

---

## 🔧 Troubleshooting

### ❌ Problema: "Não consegue encontrar .env"

- ✅ Solução: Copie `.env` para a mesma pasta do `.exe`
- ✅ Verifique se as variáveis de ambiente estão corretas

### ❌ Problema: "Selenium WebDriver não encontrado"

- ✅ A pasta `_internal/` foi copiada junto com o `.exe`?
- ✅ Execute o `.exe` manualmente uma vez para testar

### ❌ Problema: "Oracle Connection Failed"

- ✅ Oracle Instant Client está instalado?
- ✅ Variáveis de `.env` (AUSTA_BD_ORACLE, BD_USUARIO, BD_SENHA) estão corretas?
- ✅ A conexão de rede está ativa?

### ❌ Problema: "Task não executa"

- ✅ Execute o `.exe` manualmente para verificar se funciona
- ✅ Verifique se credenciais Windows estão corretas
- ✅ Confira o diretório de trabalho (Working Directory)
- ✅ Verifique o Histórico da tarefa em Task Scheduler

---

## 📊 Monitoramento

### Ver Status:

```powershell
# Ver tarefa agendada
Get-ScheduledTask -TaskName "RPA Autorizacoes PA"

# Ver histórico de execução
Get-ScheduledTaskInfo -TaskName "RPA Autorizacoes PA"

# Ver logs de evento
Get-WinEvent -LogName "System" | Where-Object {$_.ProviderName -eq "TaskScheduler"}
```

### Desabilitar/Remover:

```powershell
# Desabilitar
Disable-ScheduledTask -TaskName "RPA Autorizacoes PA"

# Remover
Unregister-ScheduledTask -TaskName "RPA Autorizacoes PA" -Confirm:$false
```

---

## 📝 Notas Importantes

- ⚠️ O arquivo `.env` deve estar **sempre** na mesma pasta do `.exe`
- ⚠️ O computador **não pode estar em sleep/hibernação** durante a execução
- ⚠️ Se precisar de acesso compartilhado de rede, use credenciais de um serviço
- ⚠️ Logs são salvos em `logs/automacao.log` e rotacionam diariamente
- ⚠️ Cada execução registra-se em `ROBO_RPA.EXECUCAO` no Oracle

---

## 🎯 Exemplo de Agendamento Comum

| Cenário | Disparador | Repetição |
|---------|-----------|-----------|
| Contínuo durante expediente | 08:00 - 18:00 | A cada 5 min |
| Noturno | 20:00 - 06:00 | A cada 10 min |
| Horário de pico | 14:00 - 15:30 | A cada 2 min |
| Uma única execução | Um horário fixo | Sem repetição |

---

## 📞 Suporte

Se encontrar erros:
1. Verifique o arquivo de log: `logs/automacao.log`
2. Procure pela mensagem de erro no histórico de eventos do Windows
3. Execute manualmente o `.exe` para debug: 
   ```bash
   C:\RPA\hos_austa_autorizacao_pre\hos_austa_autorizacao_pre.exe
   ```

---

**Documento atualizado:** 26/03/2025  
**Projeto:** HOS_AUSTA_AUTORIZACAO_PRE (Hospital Austa - RPA PA)
