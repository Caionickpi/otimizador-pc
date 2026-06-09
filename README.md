# Otimizador PC

Programa de terminal (TUI) em **português do Brasil** para **diagnóstico e
ajustes seguros** de computadores **Windows 10 e 11**.

O foco número 1 é **segurança**: o programa nunca aplica nada sem **descrever**
o que fará, **criar backup / ponto de restauração**, **pedir confirmação** e
**registrar tudo em log**. Toda alteração é **reversível**.

> Fluxo do programa: **diagnosticar → analisar/recomendar → aplicar os ajustes
> escolhidos** (sempre com backup antes).

---

## ✨ Recursos

- **Diagnóstico completo** (somente leitura): sistema, CPU, RAM (com velocidade
  dos módulos), discos (detecta **SSD x HDD** e saúde), GPU, placa-mãe/BIOS,
  rede (IP/DNS), inicialização, plano de energia e **notebook x desktop**.
- **Recomendações personalizadas** com base no hardware real (ex.: nunca sugere
  desfragmentar SSD — sugere TRIM).
- **Categorias de ajuste**, cada uma com backup + confirmação + log:
  1. Limpeza de arquivos temporários
  2. Gerenciamento de inicialização (reversível)
  3. Otimização de serviços (apenas uma *whitelist* curada)
  4. Plano de energia (adaptado a desktop/notebook)
  5. Otimização de rede (flush DNS, renovar IP, Winsock, DNS rápido)
  6. Efeitos visuais / desempenho
  7. Otimização de disco (desfragmenta só HDD; TRIM em SSD)
- **Mecanismos de segurança**: ponto de restauração do sistema, backup de
  registro (`.reg`), **modo simulação (dry-run)**, confirmação dupla, **desfazer
  última alteração** e logging completo.

---

## 🛡️ O que o programa **nunca** faz

- Nunca desativa antivírus, Windows Defender ou firewall.
- Nunca apaga arquivos pessoais (documentos, fotos, downloads, área de
  trabalho). Só mexe em **cache/temporários conhecidos**.
- Nunca toca em serviços/chaves críticos que impeçam o Windows de iniciar.
- Nunca faz alteração irreversível sem confirmação explícita e backup prévio.

---

## 📋 Requisitos

- **Windows 10 ou 11** (x64).
- **Python 3.11+** — necessário apenas para rodar a partir do código-fonte ou
  para gerar o `.exe`. O executável final **não** exige Python instalado.

---

## 🚀 Instalação (a partir do código-fonte)

1. Abra o **Prompt de Comando** ou **PowerShell** na pasta do projeto.
2. (Recomendado) crie um ambiente virtual:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale as dependências:

   ```bat
   pip install -r requirements.txt
   ```

---

## ▶️ Como rodar

```bat
python main.py
```

- O **diagnóstico** e as **recomendações** funcionam **sem** privilégios de
  administrador.
- Para **aplicar ajustes**, o programa detecta se você é administrador e, se
  não for, **oferece reabrir elevado** (vai aparecer o aviso do Windows/UAC).
- Para já começar com tudo liberado, você também pode abrir o
  **Prompt de Comando como administrador** e rodar `python main.py`.

> 💡 **Dica:** ative o **Modo simulação** (opção 10 do menu) para ver exatamente
> o que cada ajuste faria, sem alterar nada.

---

## 📦 Gerar o executável (`.exe`)

> ⚠️ **Importante:** o `.exe` precisa ser **compilado no Windows**. O PyInstaller
> não faz compilação cruzada — não dá para gerar um `.exe` do Windows a partir de
> Linux ou macOS. Use uma das três formas abaixo.

### Opção 1 — GitHub Actions (recomendada, **não precisa de Python no seu PC**)

Este repositório já vem com um fluxo de CI (`.github/workflows/build.yml`) que
**compila o `.exe` numa máquina Windows do próprio GitHub** a cada `push` para
`main`. Para baixar o executável pronto:

1. Faça o `push` do projeto para o GitHub.
2. Abra a aba **Actions** do repositório e clique na execução mais recente de
   *“Compilar OtimizadorPC (Windows .exe)”*.
3. Na seção **Artifacts**, baixe **`OtimizadorPC-windows`** (um `.zip` com o
   `OtimizadorPC.exe` dentro).

> 💡 Dá para disparar o build manualmente em **Actions → Compilar OtimizadorPC →
> Run workflow**. E, se você criar uma **tag** `v1.0.0` (por exemplo), o fluxo
> ainda publica uma **Release** com o `.exe` anexado.

### Opção 2 — `build.bat` (no seu Windows, com um duplo-clique)

Se preferir gerar localmente, basta ter o **Python 3.11+** instalado e dar um
**duplo-clique** em **`build.bat`** na raiz do projeto. Ele cria o ambiente
virtual, instala as dependências, roda o PyInstaller e deixa o resultado em
`dist\OtimizadorPC.exe`.

### Opção 3 — PyInstaller manual (avançado)

Com as dependências instaladas (o `pyinstaller` já vem no `requirements.txt`),
rode na **raiz do projeto**, no Windows, usando a receita já pronta:

```bat
pyinstaller --noconfirm --clean OtimizadorPC.spec
```

O arquivo **`OtimizadorPC.spec`** já embute a lista de serviços
(`dados\servicos_seguros.json`) e declara os *hidden imports* do WMI/pywin32
(como `win32timezone`) que o PyInstaller costuma não detectar sozinho.

Detalhes de todas as opções:

- Geram um único `OtimizadorPC.exe` em `dist\` (modo *onefile*, console).
- O executável final **não** exige Python instalado.
- As pastas `logs\` e `backups\` são criadas automaticamente **ao lado do
  `.exe`** na primeira execução.
- Por padrão, o `.exe` **não** abre pedindo administrador: o próprio programa
  oferece a elevação (UAC) só quando você escolhe aplicar um ajuste —
  comportamento recomendado, pois o diagnóstico funciona sem admin.

---

## 🗂️ Estrutura do projeto

```
otimizador-pc/
├── main.py                     # Ponto de entrada e menu principal
├── config.py                   # Constantes e estado global
├── requirements.txt
├── README.md
├── OtimizadorPC.spec           # Receita de build do PyInstaller
├── build.bat                   # Gera o .exe no Windows (duplo-clique)
├── .github/workflows/build.yml # CI: compila o .exe no Windows do GitHub
├── modulos/
│   ├── diagnostico.py          # Detecção de hardware/software (leitura)
│   ├── recomendacoes.py        # Análise do perfil + sugestões
│   ├── seguranca.py            # Restauração, backups, logging, desfazer
│   ├── interface.py            # Componentes da TUI (rich + questionary)
│   ├── elevacao.py             # Privilégios de administrador
│   └── tweaks/
│       ├── limpeza.py
│       ├── inicializacao.py
│       ├── servicos.py
│       ├── energia.py
│       ├── rede.py
│       ├── visual.py
│       └── disco.py
├── dados/
│   └── servicos_seguros.json   # Whitelist de serviços seguros
├── logs/                       # Logs (gerados em tempo de execução)
└── backups/                    # Backups de registro (.reg) e histórico
```

---

## ↩️ Como desfazer alterações

- **Desfazer última alteração** (opção 11 do menu) reverte a última mudança
  registrada (serviço, DNS, plano de energia, inicialização ou efeitos visuais).
- Os **backups de registro** ficam em `backups\*.reg`. Você pode aplicá-los
  manualmente dando duplo clique ou com `reg import "arquivo.reg"`.
- Em último caso, use a **Restauração do Sistema** do Windows (o programa cria
  um ponto antes de cada sessão de alterações).

---

## 🧾 Logs

Cada execução grava em `logs\otimizador_AAAA-MM-DD.log`, com data, hora, ação e
resultado (sucesso/erro). Veja-os pelo menu (opção 12) ou abrindo o arquivo.

---

## ⚠️ Aviso

Esta ferramenta foi feita para ser conservadora e segura, mas mexer em um
sistema operacional sempre envolve algum risco. Use com responsabilidade,
mantenha backups dos seus dados importantes e prefira o **Modo simulação** se
estiver em dúvida.
