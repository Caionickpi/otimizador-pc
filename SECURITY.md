# 🔒 Revisão de segurança e postura — Otimizador PC

> Revisão feita para o lançamento público da **v2.0** (modo janela).
> Escopo: todo o código-fonte do repositório (backend + nova camada de GUI).
> Resultado: **nenhuma vulnerabilidade crítica encontrada.** O programa segue
> boas práticas de segurança em todos os pontos sensíveis. Abaixo está o detalhe
> por área e as recomendações operacionais para a distribuição pública.

## ✅ Resumo executivo

| Área | Situação |
|------|----------|
| Execução de comandos do sistema | ✔ Sólida — sem injeção de shell |
| Atualização automática (rede) | ✔ Forte — HTTPS + SHA‑256 + validação do binário |
| Elevação de privilégio (UAC) | ✔ Padrão e correta |
| Edição de registro | ✔ Backup `.reg` antes + desfazer preciso |
| Exclusão de arquivos (limpeza) | ✔ Restrita a pastas temporárias conhecidas |
| Reversibilidade | ✔ Ponto de restauração + pilha de desfazer persistida |
| Tratamento de erros | ✔ Blindagem total — falhas não derrubam o app |

## 🔎 Detalhe por área

### 1. Execução de comandos (`modulos/seguranca.py::executar_comando`)
- Os comandos são passados como **lista de argumentos** (não string), o que
  elimina injeção de shell na esmagadora maioria dos casos.
- `subprocess.run(..., creationflags=CREATE_NO_WINDOW)` evita abrir janelas de
  console indesejadas.
- Todas as chamadas têm **timeout** e capturam exceções; uma falha de comando
  retorna `(-1, "", erro)` em vez de propagar.
- **PowerShell:** usado com `-NoProfile -NonInteractive -ExecutionPolicy Bypass`.
  O `Bypass` é **local ao processo** (não altera a política da máquina) e é a
  forma recomendada de rodar cmdlets pontuais. O único valor interpolado em uma
  string de comando é a *descrição* do ponto de restauração — uma **constante
  interna** do programa, com aspas sanitizadas. Sem entrada do usuário ali.

### 2. Atualização automática (`modulos/atualizacao.py`)
Esta é a área de maior superfície (baixa e executa um binário pela rede). Está
bem protegida:
- Consulta apenas a **API pública e HTTPS** do GitHub (URL fixa em `config.py`).
- O download vem do `browser_download_url` do próprio release (HTTPS).
- Antes de aplicar, o arquivo é validado em **três camadas**:
  1. **tamanho** igual ao informado pela API;
  2. **assinatura PE** (`MZ`) — rejeita HTML de erro / arquivo truncado;
  3. **SHA‑256** conferido contra o *digest* publicado pelo GitHub.
- A troca do executável é feita por um `.bat` auxiliar **com limite de tentativas**
  (nunca entra em laço infinito) e mensagens claras de falha.
- Tudo exige **confirmação** do usuário e respeita o **modo simulação**.

> Observação de confiança: o SHA‑256 vem da mesma resposta da API que traz a URL
> — ou seja, a âncora de confiança é o TLS do GitHub. Isso é adequado para o
> modelo de distribuição atual. Veja em *Recomendações* a evolução possível
> (assinatura de release com chave própria).

### 3. Elevação de privilégio (`modulos/elevacao.py`)
- Usa `ShellExecuteW` com o verbo `runas`, disparando o **UAC** do Windows — o
  caminho oficial e esperado. Sem truques de auto‑elevação silenciosa.
- Diagnóstico e recomendações funcionam **sem** admin; só os ajustes pedem
  elevação, e o usuário decide.

### 4. Registro do Windows
- Toda chave editada é **exportada para `.reg`** (backup) antes da alteração.
- O rollback é **preciso** (restaura/remove valor a valor) e fica numa pilha de
  desfazer persistida em disco — permite "Reverter tudo".

### 5. Exclusão de arquivos (`modulos/tweaks/limpeza.py`)
- Opera **apenas** sobre uma lista curada de pastas temporárias.
- **Protege** os arquivos do próprio programa (pasta `_MEIPASS` do `.exe`).
- **Não segue** symlinks/junções para fora do alvo; arquivos em uso são pulados.

### 6. Nova camada de GUI (`gui/`)
- É uma **casca visual**: não reimplementa lógica de otimização. Ela apenas
  substitui, em tempo de execução, as primitivas de interface (confirmações,
  menus, progresso) por equivalentes gráficos — então **toda a segurança do
  backend continua valendo** (backups, confirmações, simulação, desfazer).
- O backend roda numa thread separada; a janela permite **uma tarefa por vez** e
  as confirmações continuam sendo **explícitas** (diálogos nativos).

## 🛡️ Recomendações para a distribuição pública

Estas são melhorias **operacionais** (não há bug a corrigir no código):

1. **Assinatura de código (Authenticode).** Assinar o `OtimizadorPC.exe` com um
   certificado reduz bastante o atrito com o SmartScreen e antivírus — importante
   para um programa que o usuário roda como administrador. (Sem isso, alguns AVs
   podem alertar na 1ª execução; o UPX já foi desativado de propósito por esse
   motivo.)
2. **Assinatura de releases (evolução do auto‑update).** No futuro, publicar um
   `.sig`/hash assinado com chave própria e verificá‑lo no cliente tornaria a
   atualização independente da confiança no transporte.
3. **Manter `dados/servicos_seguros.json` como whitelist** — nunca migrar para
   blacklist. A abordagem atual (só toca no que é conhecido) é a correta.

## 📣 Como relatar uma vulnerabilidade

Encontrou um problema de segurança? Abra uma *issue* **sem detalhes sensíveis**
pedindo contato, ou escreva diretamente ao mantenedor. Agradecemos relatos
responsáveis.
