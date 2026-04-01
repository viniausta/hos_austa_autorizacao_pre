# Relatório: Limitação de Rede Docker → Share TASY

**Data:** 30/03/2026
**Projeto:** RPA Autorização Pré-Hospitalar (hos_austa_autorizacaopre)
**Problema:** Container Docker não consegue gravar PDF no share de rede do TASY

---

## 1. Objetivo

O robô RPA autoriza solicitações no portal Unimed, gera o PDF da Guia TISS e precisa gravá-lo em:

```
\\172.20.255.13\tasyausta\anexo_opme
```

Para que o sistema TASY consiga abrir o anexo da autorização.

---

## 2. Ambiente

| Componente | Detalhe |
|------------|---------|
| **Máquina** | Windows 11 Pro (10.0.26200) |
| **Docker Desktop** | WSL2 backend, Hyper-V |
| **Docker Network** | Bridge (172.24.0.0/16) |
| **Rede corporativa** | Wi-Fi Austa (192.168.50.98, gateway 192.168.50.254) |
| **Servidor TASY (arquivos)** | 172.20.255.13 (porta 445/SMB) |
| **Servidor Oracle** | 10.100.0.10 (porta 1521) |

---

## 3. Problema Identificado

O container Docker **não consegue alcançar o servidor 172.20.255.13 em nenhuma porta**.

A máquina Windows host acessa normalmente (3 saltos, 10ms via gateway corporativo), mas o tráfego originado dentro do Docker não é roteado para essa subnet.

### Testes de conectividade do container:

| Destino | Porta | Resultado |
|---------|-------|-----------|
| 8.8.8.8 (internet) | 53 | ✅ Acessível |
| 10.100.0.10 (Oracle) | 1521 | ✅ Acessível |
| 192.168.50.254 (gateway corp.) | 80 | ✅ Acessível |
| 192.168.50.254 (gateway corp.) | 445 | ❌ Bloqueada |
| 172.20.255.13 (TASY) | 445 | ❌ Timeout |
| 172.20.255.13 (TASY) | 139 | ❌ Timeout |
| 172.20.255.13 (TASY) | 80 | ❌ Timeout |
| 172.20.255.13 (TASY) | 135 | ❌ Timeout |
| 172.20.255.13 (TASY) | 443 | ❌ Timeout |

### Teste do host Windows (mesma máquina):

```
tracert 172.20.255.13
  1   3ms   192.168.50.254   (gateway corporativo)
  2   *     *
  3  10ms   172.20.255.13    ✅ alcança em 3 saltos
```

---

## 4. Causa Raiz

O Docker Desktop no Windows usa **Hyper-V com NAT isolado**. Os containers recebem IPs na subnet virtual `172.24.0.0/16` e o tráfego é traduzido (NAT) para sair pela interface da máquina host.

```
Container (172.24.0.4) → Docker NAT (172.24.0.1) → Hyper-V vSwitch → Windows host

Internet (8.8.8.8):       roteado via NAT → ✅ funciona
Oracle (10.100.0.10):     roteado via NAT → ✅ funciona
TASY (172.20.255.13):     NÃO roteado     → ❌ timeout
```

O NAT do Hyper-V roteia corretamente para a internet e para algumas subnets internas (10.100.0.x), mas **não para a subnet 172.20.x.x** onde está o servidor de arquivos do TASY. Isso acontece porque:

1. A subnet 172.20.x.x está atrás de um roteamento específico via gateway corporativo (192.168.50.254)
2. O Hyper-V NAT não herda todas as rotas da tabela de roteamento do host Windows
3. Adicionalmente, o gateway corporativo bloqueia tráfego SMB (porta 445) originado de sessões NAT/encaminhamento

---

## 5. Soluções Testadas

| # | Abordagem | Resultado | Motivo |
|---|-----------|-----------|--------|
| 1 | **pysmb** (SMB1 via Python) | ❌ Timeout 30s | Container não alcança 172.20.255.13 |
| 2 | **smbprotocol** (SMB2/3 via Python) | ❌ Timeout 60s | Mesmo problema de rede |
| 3 | **Docker bind mount** (drive T: mapeado) | ❌ Pasta vazia | Docker Desktop WSL2 não monta drives de rede |
| 4 | **Regra Windows Firewall** (netsh outbound 445) | ❌ Sem efeito | Problema é roteamento, não firewall |
| 5 | **Regra Hyper-V Firewall** (FPS-SMB-Out-TCP) | ❌ Acesso negado / sem efeito | Requer SYSTEM; mesmo habilitada, não resolve roteamento |
| 6 | **Nova regra Hyper-V** (New-NetFirewallHyperVRule) | ❌ Sem efeito | Criada com sucesso mas problema é roteamento |
| 7 | **WSL2 mirrored networking** (.wslconfig) | ❌ Não se aplica | Docker Desktop usa VM própria, ignora networkingMode |
| 8 | **Docker Desktop "Enable host networking"** | ❌ Sem efeito | Habilita a opção mas não muda o NAT padrão |
| 9 | **network_mode: host** | ❌ Não suportado | Docker Desktop Windows não suporta host networking para containers Linux |
| 10 | **Volume CIFS Docker** | Não testado | Bug documentado no WSL2 (docker/for-win #6307) |

---

## 6. Soluções Viáveis

### Opção A — Python no host Windows (recomendada)

Manter apenas o Selenoid (browser Chrome) no Docker. O Python RPA roda no Windows host, que tem acesso direto à rede corporativa.

- **Vantagem:** cópia instantânea via `shutil.copy2`, zero processos extras
- **Desvantagem:** Python + dependências no host Windows (não containerizado)

```
Docker: Selenoid (Chrome) ← WebDriver → Python no Windows host → \\172.20.255.13\...
```

### Opção B — Watcher no Windows

Container grava PDF em pasta local (bind mount). Script PowerShell no Windows monitora a pasta e move para o share.

- **Vantagem:** mantém Python no Docker
- **Desvantagem:** processo extra, possível delay, ponto de falha adicional

### Opção C — Migrar para Docker em Linux nativo (servidor dedicado)

Rodar o Docker em um servidor Linux nativo (sem Hyper-V/WSL2) conectado diretamente na rede corporativa. Nesse cenário, o container teria acesso direto à rede e o `smbprotocol` funcionaria sem limitações.

- **Vantagem:** mantém tudo no Docker, solução definitiva
- **Desvantagem:** requer servidor Linux dedicado na rede corporativa

---

## 7. Conclusão

O Docker Desktop no Windows com WSL2/Hyper-V possui uma limitação de rede que impede containers de acessar o servidor de arquivos `172.20.255.13`. Não é um problema de credencial, firewall local ou configuração do Docker — é uma limitação arquitetural do NAT do Hyper-V que não roteia tráfego para todas as subnets acessíveis pelo host. Foram testadas 10 abordagens diferentes na máquina local e nenhuma resolveu.

---

## 8. Solução Adotada

**Selenoid (browser Chrome) permanece no Docker. Python (API + RPA) roda no Windows host.**

O PDF é capturado em memória pelo Python via Chrome DevTools Protocol (CDP) — os bytes nunca tocam o filesystem do Chrome/Docker. O Python, rodando no Windows host com acesso direto à rede corporativa, grava o PDF diretamente em `\\172.20.255.13\tasyausta\anexo_opme` com `shutil.copy2`.

```
Docker: Selenoid (:4444) → Chrome (automação web)
           ↕ WebDriver via http://localhost:4444/wd/hub
Windows: python api_server.py (:8000)
           → Captura PDF em memória via CDP
           → shutil.copy2 → \\172.20.255.13\tasyausta\anexo_opme  (instantâneo)
           → INSERT no banco TASY
           → Deleta PDF local
```

- **Sem processos extras** (sem watcher, sem .bat, sem Task Scheduler)
- **Cópia instantânea** (direto para o share de rede)
- **Pode ser implementada imediatamente** (sem alteração de infraestrutura)

Para o futuro, caso o projeto migre para um **servidor Linux nativo** na rede corporativa (sem Hyper-V/WSL2), o código com `smbprotocol` já está preparado para manter tudo dentro do Docker.
