<div align="center">

# ⚙️ Otimizador PC

### Diagnóstico e ajustes **seguros** para Windows 10 e 11 — direto do terminal, em português 🇧🇷

[![Build do .exe (Windows)](https://github.com/Caionickpi/otimizador-pc/actions/workflows/build.yml/badge.svg)](https://github.com/Caionickpi/otimizador-pc/actions/workflows/build.yml)
![Versão](https://img.shields.io/badge/vers%C3%A3o-1.4.0-blue)
![Plataforma](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Interface](https://img.shields.io/badge/TUI-rich%20%2B%20questionary-ff69b4)
![Idioma](https://img.shields.io/badge/idioma-Portugu%C3%AAs%20(BR)-009C3B)

</div>

---

O **Otimizador PC** é um programa de terminal (TUI) que **diagnostica** o seu
computador, **recomenda** melhorias com base no hardware real e **aplica
ajustes seguros** — sempre com **backup**, **confirmação** e **registro em
log**. O foco número 1 é **segurança**: **toda alteração é reversível** e nada
acontece sem você aprovar.

> **Fluxo:** 🔍 diagnosticar → 💡 analisar/recomendar → 🛠️ aplicar só o que você escolher *(com backup antes)*.

## 📑 Índice

- [✨ Recursos](#-recursos)
- [🔥 Aba Avançados (jogos e desempenho)](#-aba-avançados-jogos-e-desempenho)
- [🖱 Reduzir input lag](#-reduzir-input-lag-mouse-teclado-monitor)
- [🎯 Otimização por jogo](#-otimização-por-jogo)
- [🔄 Atualização automática](#-atualização-automática)
- [🛡️ O que o programa nunca faz](#️-o-que-o-programa-nunca-faz)
- [🖼️ Prévia da interface](#️-prévia-da-interface)
- [📥 Baixar o executável (.exe)](#-baixar-o-executável-exe-pronto)
- [▶️ Rodar a partir do código](#️-rodar-a-partir-do-código-fonte)
- [🔨 Gerar o executável você mesmo](#-gerar-o-executável-você-mesmo)
- [🗂️ Estrutura do projeto](#️-estrutura-do-projeto)
- [↩️ Como desfazer alterações](#️-como-desfazer-alterações)
- [🧾 Logs](#-logs)
- [❓ Perguntas frequentes](#-perguntas-frequentes)
- [⚠️ Aviso](#️-aviso)

---

## ✨ Recursos

- **🔍 Diagnóstico completo** (somente leitura): sistema, CPU, RAM (com
  velocidade dos módulos), discos (detecta **SSD × HDD** e saúde), GPU,
  placa-mãe/BIOS, rede (IP/DNS), inicialização, plano de energia e
  **notebook × desktop**.
- **💡 Recomendações personalizadas** com base no hardware real (ex.: nunca
  sugere desfragmentar SSD — sugere TRIM).
- **🛠️ Categorias de ajuste**, cada uma com backup + confirmação + log:

  | # | Categoria | O que faz |
  |---|-----------|-----------|
  | 🧹 | **Limpeza** | Remove temporários, cache do Windows Update, Lixeira e miniaturas |
  | 🚀 | **Inicialização** | Liga/desliga programas que abrem com o Windows (reversível) |
  | 🛠 | **Serviços** | Ajusta apenas serviços de uma *whitelist* curada e segura |
  | 🔋 | **Energia** | Planos adaptados a desktop/notebook |
  | 🌐 | **Rede** | Flush DNS, renovar IP, resetar Winsock, DNS mais rápido |
  | ✨ | **Efeitos visuais** | Prioriza desempenho desligando animações pesadas |
  | 💽 | **Disco** | Desfragmenta **só HDD**; faz **TRIM** em SSD |
  | 🔥 | **Avançado** | Otimizações "pesadas" para **jogos e desempenho máximo** (risco médio/alto) — veja abaixo |
  | 🖱 | **Input lag** | Reduz a **latência de entrada** de **mouse, teclado e monitor** (a maioria **sem admin**) |
  | 🎯 | **Por jogo** | **Detecta os jogos instalados** e otimiza o PC para o jogo escolhido, adaptado ao hardware |

- **🔄 Atualização automática**: verifica novas versões no GitHub e, no `.exe`,
  **baixa e se atualiza sozinho** (com a sua confirmação).
- **🔒 Mecanismos de segurança**: ponto de restauração do sistema, backup de
  registro (`.reg`), **modo simulação (dry-run)**, confirmação dupla,
  **desfazer última alteração** e logging completo.

## 🔥 Aba Avançados (jogos e desempenho)

> ⚠️ **Atenção:** esta é a parte **"pesada"** da otimização — ajustes de **risco
> médio/alto** para usuários avançados. Vários exigem **administrador** e/ou
> **reiniciar** o PC. **Todos continuam reversíveis** (backup `.reg` + ponto de
> restauração + *Desfazer última alteração*), e cada um **avisa os riscos**
> antes de aplicar. Na dúvida, use o **Modo simulação**.

**🎮 Jogos**

| Ajuste | O que faz | Risco |
|--------|-----------|:-----:|
| **Modo Jogo + desativar Game DVR** | Liga o Modo Jogo e desliga a gravação em segundo plano (consome CPU/GPU) | 🟡 Baixo–médio |
| **Prioridade para jogos (MMCSS)** | Ajusta MMCSS e o agendador da CPU para priorizar o jogo em primeiro plano | 🟠 Médio |
| **Agendamento de GPU por hardware (HAGS)** | Ativa o *Hardware-Accelerated GPU Scheduling* (reinício) | 🟠 Médio |
| **Reduzir latência de rede (Nagle)** | Desativa o algoritmo de Nagle nas interfaces ativas para baixar o ping | 🟠 Médio |

**⚡ Desempenho geral**

| Ajuste | O que faz | Risco |
|--------|-----------|:-----:|
| **Plano "Desempenho Máximo"** | Cria/ativa o plano *Ultimate Performance* (sem economias de energia) | 🟠 Médio |
| **Desativar limitação de energia da CPU** | Desliga o *Power Throttling* | 🟠 Médio |
| **Manter o kernel na RAM** | `DisablePagingExecutive` (recomendado com 8 GB+; reinício) | 🟠 Médio |
| **Desativar hibernação** | Remove o `hiberfil.sys` e libera vários GB de disco | 🟠 Médio |

> 💡 Os ajustes de energia (Plano Máximo, *Power Throttling*) **não** são
> indicados para notebook na bateria, pois aumentam o consumo e o aquecimento.

## 🖱 Reduzir input lag (mouse, teclado, monitor)

Ajustes focados na **latência de entrada** — aquele atraso entre você mexer no
periférico e a tela responder. **A maioria fica em `HKCU`, então não exige
administrador**, e tudo é reversível em *Desfazer última alteração*.

| Pacote | O que faz | Risco |
|--------|-----------|:-----:|
| **🖱 Mouse 1:1** | Desativa a *precisão aprimorada do ponteiro* (aceleração) e fixa a sensibilidade no padrão 6/11 — movimento **linear** com a mira | 🟢 Baixo |
| **⌨ Teclado responsivo** | Desliga Teclas de Aderência/Filtragem/Alternância (o atraso e o atalho do Shift 5×) e coloca a **repetição de tecla** no mais rápido | 🟢 Baixo |
| **🖥 Monitor/exibição** | Desativa as **Otimizações de Tela Cheia (FSE)** e o Game DVR — caminho de **menor latência de apresentação** | 🟠 Médio |
| **⚡ Aplicar tudo** | Aplica os três pacotes de uma vez | 🟢🟠 Baixo–médio |

> 💡 A maior parte dos efeitos de mouse/teclado entra em vigor após
> **logoff/login** (ou reiniciar). Como sempre, dá para reverter tudo.

## 🎯 Otimização por jogo

Uma **experiência única para cada PC**: o programa detecta o hardware
**rapidamente** (≈ instantâneo), monta um **perfil da sua máquina** e usa isso
para adaptar os ajustes. Depois, **detecta os jogos instalados** (Steam e Epic)
e otimiza o PC para o jogo que você escolher.

**Como funciona:**

1. Detecta os componentes (CPU/GPU/RAM/disco, notebook × desktop) — leitura
   rápida, via registro/WMI (sem travar).
2. Lista os **jogos instalados** que encontrar (ou você informa o `.exe`).
3. Você **escolhe um jogo** e o programa aplica um perfil sob medida:
   - **Para o jogo** (sem admin): força a **GPU dedicada** (ótimo em notebook
     híbrido) e **desativa as otimizações de tela cheia** do executável.
   - **No sistema**: Modo Jogo, Game DVR desligado, prioridade para jogos
     (MMCSS) e agendamento de GPU por hardware (HAGS).
   - **Jogo competitivo** (CS2, Valorant, LoL…): inclui **redução de latência
     de rede** (Nagle).

> ✅ Como tudo no programa, **é reversível**: cada otimização por jogo registra
> um "desfazer" preciso (restaura/remap o que mudou) e respeita o **Modo
> simulação**.

## 🔄 Atualização automática

O programa **se mantém atualizado sozinho**. Ao abrir, ele faz uma checagem
rápida e silenciosa no GitHub (sem incomodar se você estiver offline ou já na
última versão). Há também a opção **`🔄 Verificar atualizações`** no menu.

Quando existe uma versão mais nova, ele mostra as novidades e, **com a sua
confirmação**, no `.exe` ele **baixa a nova versão, fecha, troca o executável e
reabre já atualizado** — sem você precisar baixar nada à mão. Se algo falhar
(antivírus, rede), ele abre a **página de download** como plano B.

> ℹ️ O download automático usa a **API pública de releases** do GitHub — por
> isso o repositório precisa estar **público**. Rodando pelo código-fonte (não
> pelo `.exe`), ele apenas avisa e abre a página de download.

## 🛡️ O que o programa **nunca** faz

- ❌ Nunca desativa antivírus, Windows Defender ou firewall.
- ❌ Nunca apaga arquivos pessoais (documentos, fotos, downloads, área de
  trabalho). Só mexe em **cache/temporários conhecidos**.
- ❌ Nunca toca em serviços/chaves críticos que impeçam o Windows de iniciar.
- ❌ Nunca faz alteração irreversível sem confirmação explícita e backup prévio.

## 🖼️ Prévia da interface

```text
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║      ⚙  Otimizador PC  v1.4.0                                      ║
║                                                                    ║
║      Diagnóstico e ajustes seguros para Windows 10 e 11            ║
║                                                                    ║
║      🛡  Sempre cria backup e pede confirmação antes de mexer.      ║
║      Nada é alterado sem a sua aprovação.                          ║
║                                                                    ║
║      Foco total em segurança e reversibilidade.                    ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ⚙  Otimizador PC  v1.4.0                                          ┃
┃  Privilégio: ✔ administrador   │   🧪 Simulação: ○ desligado       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

  » Escolha uma opção:  (use as setas, Enter para confirmar)

    1)  🔍  Diagnóstico do computador
    2)  💡  Recomendações personalizadas
    ─── Ajustes ───
    3)  🧹  Limpeza de arquivos temporários
    4)  🚀  Gerenciar inicialização
    5)  🛠  Otimizar serviços
    6)  🔋  Plano de energia
    7)  🌐  Otimização de rede
    8)  ✨  Efeitos visuais / desempenho
    9)  💽  Otimização de disco
    ─── Avançado · risco ───
   10)  🔥  Otimizações avançadas (jogos e desempenho)
   11)  🖱  Reduzir input lag (mouse/teclado/monitor)
    ─── Por jogo ───
   12)  🎯  Otimizar para um jogo (detecta no PC)
    ─── Ferramentas ───
   13)  🧪  Modo simulação (ligar)
   14)  ↩  Desfazer última alteração
   15)  📜  Ver logs
   16)  🔄  Verificar atualizações
    0)  🚪  Sair
```

## 📥 Baixar o executável (.exe) pronto

A forma mais fácil — **não precisa instalar Python**:

1. Vá em **[Releases](https://github.com/Caionickpi/otimizador-pc/releases)** e
   baixe o `OtimizadorPC.exe` da versão mais recente; **ou**
2. Vá na aba **[Actions](https://github.com/Caionickpi/otimizador-pc/actions/workflows/build.yml)**,
   abra a execução mais recente e baixe o artifact **`OtimizadorPC-windows`**.

Depois é só **dar um duplo-clique**. Para aplicar ajustes, clique com o botão
direito → **“Executar como administrador”** *(o diagnóstico e as recomendações
funcionam sem admin)*.

## ▶️ Rodar a partir do código-fonte

Requer **Windows 10/11** e **Python 3.11+**.

```bat
:: 1) (recomendado) crie um ambiente virtual
python -m venv .venv
.venv\Scripts\activate

:: 2) instale as dependências
pip install -r requirements.txt

:: 3) rode
python main.py
```

> 💡 **Dica:** ative o **Modo simulação** (opção 12) para ver exatamente o que
> cada ajuste faria, **sem alterar nada**.

## 🔨 Gerar o executável você mesmo

> ⚠️ O `.exe` precisa ser **compilado no Windows** — o PyInstaller não faz
> compilação cruzada (não dá para gerar um `.exe` a partir de Linux/macOS).

| Forma | Como | Precisa de Python? |
|-------|------|:------------------:|
| 🤖 **GitHub Actions** | Já configurado: a cada `push`, o `.exe` é compilado numa máquina Windows do GitHub e fica disponível em **Actions → Artifacts** | ❌ Não |
| 🖱️ **`build.bat`** | **Duplo-clique** no arquivo `build.bat` na raiz do projeto | ✅ Sim |
| ⌨️ **PyInstaller** | `pyinstaller --noconfirm --clean OtimizadorPC.spec` | ✅ Sim |

O resultado é um único `dist\OtimizadorPC.exe` (modo *onefile*, console). As
pastas `logs\` e `backups\` são criadas **ao lado do `.exe`** na primeira
execução. A receita `OtimizadorPC.spec` já embute a whitelist de serviços e os
*hidden imports* do WMI/pywin32 (como `win32timezone`).

## 🗂️ Estrutura do projeto

```text
otimizador-pc/
├── main.py                     # Ponto de entrada e menu principal
├── config.py                   # Constantes, versão e estado global
├── requirements.txt
├── OtimizadorPC.spec           # Receita de build do PyInstaller
├── build.bat                   # Gera o .exe no Windows (duplo-clique)
├── .github/workflows/build.yml # CI: compila o .exe no Windows do GitHub
├── modulos/
│   ├── diagnostico.py          # Detecção de hardware/software (leitura, rápida)
│   ├── hardware.py             # Perfil de otimização por máquina (escalabilidade)
│   ├── jogos.py                # Detecção de jogos instalados (Steam/Epic)
│   ├── recomendacoes.py        # Análise do perfil + sugestões
│   ├── seguranca.py            # Restauração, backups, logging, desfazer
│   ├── interface.py            # Componentes da TUI (rich + questionary)
│   ├── elevacao.py             # Privilégios de administrador (UAC)
│   ├── atualizacao.py          # 🔄 Auto-update via GitHub Releases
│   └── tweaks/
│       ├── limpeza.py
│       ├── inicializacao.py
│       ├── servicos.py
│       ├── energia.py
│       ├── rede.py
│       ├── visual.py
│       ├── disco.py
│       ├── avancado.py         # 🔥 Otimizações avançadas (jogos/desempenho)
│       ├── inputlag.py         # 🖱 Reduzir input lag (mouse/teclado/monitor)
│       └── otimizar_jogo.py    # 🎯 Otimização por jogo (detecta + adapta)
├── dados/
│   └── servicos_seguros.json   # Whitelist de serviços seguros
├── logs/                       # Logs (gerados em tempo de execução)
└── backups/                    # Backups de registro (.reg) e histórico
```

## ↩️ Como desfazer alterações

- **Desfazer última alteração** (opção 13) reverte a última mudança registrada
  (serviço, DNS, plano de energia, inicialização ou efeitos visuais).
- Os **backups de registro** ficam em `backups\*.reg` — aplique-os manualmente
  com duplo-clique ou `reg import "arquivo.reg"`.
- Em último caso, use a **Restauração do Sistema** do Windows (o programa cria
  um ponto antes de cada sessão de alterações).

## 🧾 Logs

Cada execução grava em `logs\otimizador_AAAA-MM-DD.log`, com data, hora, ação e
resultado (sucesso/erro). Veja-os pelo menu (opção 14) ou abrindo o arquivo.

## ❓ Perguntas frequentes

<details>
<summary><b>Preciso ser administrador?</b></summary>

Não para **diagnosticar** e ver **recomendações**. Para **aplicar ajustes**, o
programa detecta se você é admin e, se não for, oferece reabrir elevado (vai
aparecer o aviso do Windows/UAC).
</details>

<details>
<summary><b>É seguro? Pode quebrar meu Windows?</b></summary>

O programa é conservador: só mexe em itens conhecidos de uma lista curada,
sempre cria backup antes e pede confirmação. Ainda assim, mexer no sistema
sempre envolve algum risco — mantenha backups dos seus dados e use o
**Modo simulação** se estiver em dúvida.
</details>

<details>
<summary><b>O antivírus reclamou do .exe. É vírus?</b></summary>

Não. É um falso positivo comum com executáveis gerados por PyInstaller. Por
isso a compressão UPX foi **desligada** de propósito, para reduzir esses
alertas. Você pode compilar o `.exe` você mesmo (veja acima) se preferir.
</details>

<details>
<summary><b>Funciona no Windows 7 / 8?</b></summary>

O alvo oficial é **Windows 10 e 11** (x64). Em versões mais antigas, parte das
detecções (ex.: SSD × HDD) pode não funcionar.
</details>

## ⚠️ Aviso

Esta ferramenta foi feita para ser conservadora e segura, mas mexer em um
sistema operacional sempre envolve algum risco. Use com responsabilidade,
mantenha backups dos seus dados importantes e prefira o **Modo simulação** se
estiver em dúvida.

<div align="center">

---

Feito com ❤️ e 🐍 para deixar o Windows mais rápido **com segurança**.

</div>
