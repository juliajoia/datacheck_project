# DataCheck

**Dados confiáveis. Decisões inteligentes.**

Plataforma web que acompanha o ciclo completo de preparação dos dados:
**Diagnosticar → Corrigir → Validar → Exportar → Explorar → Gerar relatórios.**
Envie uma planilha CSV/XLSX, receba o diagnóstico, trate as inconsistências com sugestões explicáveis,
baixe a base tratada e gere um relatório de análise exploratória (EDA) em PDF ou Excel.

| Camada | Tecnologia |
|---|---|
| Frontend (`datacheck_front/`) | React 18 · Vite · TypeScript · Tailwind CSS · shadcn/ui (Radix) · React Router · Recharts · TanStack Table · Axios · React Hook Form · Zod · Lucide |
| Backend (`datacheck_back/`) | Python 3.12+ · FastAPI · Pandas/NumPy · OpenPyXL · SQLAlchemy 2 · Alembic · Pydantic · Argon2 · Pytest |
| Banco | PostgreSQL 16 (`docker-compose.yml`) |

Frontend e backend são projetos independentes e se comunicam por API REST (documentação interativa em `/docs`).

## Estrutura

```
datacheck_project/
├── docker-compose.yml           # PostgreSQL local
├── datacheck_back/
│   ├── app/
│   │   ├── main.py              # app FastAPI, CORS, tratamento de erros
│   │   ├── api/                 # rotas: auth (opcional), analyses, dashboard, meta
│   │   ├── core/                # config, segurança (Argon2/JWT), catálogo, parsing
│   │   ├── models/              # SQLAlchemy: users, analyses, validation_issues, analysis_feedback
│   │   ├── schemas/             # Pydantic (configuração das regras, auth, feedback)
│   │   ├── validators/          # motor de validação: 6 regras independentes (Pandas)
│   │   ├── services/            # leitura de arquivos, análise, score, insights, relatórios, dashboard
│   │   │   ├── cleaning/        # tratamento: tipos de variável, imputação, duplicidades, correções, versões, exportação
│   │   │   └── eda/             # análise exploratória: estatísticas, gráficos, PDF/XLSX, geração em segundo plano
│   │   ├── database/            # engine e sessão
│   │   └── scripts/             # export_feedback
│   ├── alembic/                 # migrações
│   ├── data/sample/             # 2 bases fictícias + gabaritos + gerador
│   └── tests/
├── datacheck_front/
│   └── src/ components/ pages/ layouts/ hooks/ services/ types/ contexts/ utils/
└── docs/VALIDACAO.md            # modelo para a validação acadêmica (Lean, hipóteses, evidências)
```

## Executar localmente

Requisitos: Python 3.12+, Node 20+, Docker.

```bash
# 1) Banco
docker compose up -d db

# 2) Backend  (http://localhost:8000 · docs em /docs)
cd datacheck_back
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # ajuste DATACHECK_SECRET_KEY
alembic upgrade head            # cria as tabelas
uvicorn app.main:app --reload --port 8000

# 3) Frontend  (http://localhost:5173)
cd datacheck_front
cp .env.example .env
npm install
npm run dev
```

Abra http://localhost:5173 e use *Nova análise → Base de demonstração*. **O login é opcional**: o app funciona
como visitante; o avatar redondo no canto superior direito oferece *Entrar* e *Criar conta*.
Em desenvolvimento o Vite faz proxy de `/api` para o backend (mesma origem, sem CORS).

Scripts do frontend: `npm run dev` · `npm run build` · `npm run typecheck`.

### Variáveis de ambiente (backend, prefixo `DATACHECK_`)

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://datacheck:datacheck@localhost:5432/datacheck` | Conexão |
| `SECRET_KEY` | (dev) | Assinatura da sessão (login opcional). **Obrigatória em produção** |
| `ENVIRONMENT` | `development` | Com `production`, recusa o segredo padrão |
| `COOKIE_SECURE` | `false` | `true` em HTTPS |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Origens permitidas |
| `MAX_UPLOAD_MB` | `10` | Limite de upload |
| `UPLOAD_TTL_MINUTES` | `60` | Validade do arquivo temporário |
| `DATA_DIR` | `datacheck_back/data/storage` | Armazenamento privado das bases tratadas e relatórios EDA |
| `DATA_RETENTION_DAYS` | `30` | Dias até as bases armazenadas expirarem (indicadores e ocorrências permanecem) |
| `MAX_VERSIONS` | `50` | Máximo de versões por análise |

## Fluxo da análise

1. `POST /api/analyses/upload` — recebe o arquivo (multipart), valida e lê com Pandas, guarda **temporariamente**
   (diretório privado, nome aleatório) e devolve o perfil: linhas, colunas, tipos, prévia e sugestão de configuração.
2. `POST /api/analyses/{id}/run` — executa as regras escolhidas, grava ocorrências e indicadores no PostgreSQL e
   **apaga o arquivo temporário**. Executar duas vezes a mesma análise é bloqueado (409).
3. Tratamento: `GET /api/analyses/{id}/cleaning/{summary|options|issues|duplicates|history|export}`, `POST …/cleaning/{preview|apply|undo|validate|outliers}`, `PUT …/cleaning/column-types`, `GET …/versions`, `POST …/versions/{n}/restore`. EDA: `GET …/eda/options`, `POST …/eda/generate`, `GET /api/eda`, `GET|DELETE /api/eda/{id}`, `GET /api/eda/{id}/download?format=pdf|xlsx`, `POST /api/eda/{id}/regenerate`.
4. `GET /api/analyses/{id}`, `/issues`, `/export?format=csv|xlsx` (relatório completo), `/export/issues?format=xlsx|pdf` (tabela de inconsistências com as colunas da visão detalhada; o PDF mostra até 3000 ocorrências), `POST /feedback`, `DELETE`.

Uploads abandonados são removidos pela limpeza automática (a cada upload e na inicialização).

## Tratamento de dados

Disponível nos detalhes de cada análise (botão **Tratar dados**) e pelo **Histórico → Continuar tratamento**.
Nada é aplicado sem a sua confirmação: toda correção passa por **prévia → confirmação → aplicação**, e cada aplicação
cria uma **nova versão** imutável da base. A versão 0 (a planilha enviada) nunca é sobrescrita.

- **Tipo estatístico das variáveis** (não só o tipo de armazenamento): quantitativa discreta/contínua, qualitativa nominal/ordinal,
  data/temporal e **identificador**. CPF, CEP, códigos IBGE e IDs não viram "números". A classificação é editável (ordinais com ordem própria).
- **Valores ausentes**: média, mediana, moda, valor personalizado, **imputação por grupo** (uma ou mais colunas, com mínimo de observações e alternativa
  quando o grupo é insuficiente), **interpolação linear** (exige coluna de ordenação; não extrapola), "Não informado" e manter ausente (decisão registrada).
  Variáveis discretas ficam inteiras e não negativas quando o domínio observado é não negativo. Texto em coluna numérica exige confirmação explícita.
- **Método recomendado pelo DataCheck**: heurística documentada na própria tela (assimetria, valores extremos por 1,5×IQR, % de ausência,
  nº de observações, η² de colunas de agrupamento…). É uma sugestão, não uma garantia; a distribuição observada não revela por que o dado está ausente.
  Ausência ≥ 20% gera alerta de viés; identificadores exigem revisão manual; sem observações suficientes não se recomenda imputar.
- **Duplicatas**: grupos lado a lado, escolha manual do registro a manter, ou primeiro/último/mais recente/mais completo; duplicidade por colunas-chave
  distingue duplicata exata de **conflito**; **mesclagem assistida** (conflitos exigem escolha explícita); manter ambos com justificativa.
- **Outras correções**: valor manual, marcar como ausente, converter formato numérico/de data, **valores extremos** (IQR, z-score ou limites do usuário, com a
  justificativa estatística e o aviso de que atípico ≠ erro; substituir por limites só com autorização explícita), inversão provável latitude/longitude
  (sugestão), remover registros e aceitar ocorrência como exceção (justificativa obrigatória).
- **Histórico de correções** (quem, quando, tipo, coluna, registros, valores antes/depois, método, justificativa), **desfazer**, **restaurar versão** e
  **restaurar base original**. Edições concorrentes são detectadas (a versão-base precisa coincidir).
- **Validar base tratada**: reexecuta as regras e compara antes × depois (registros, ocorrências, linhas afetadas, score, imputados, removidos,
  duplicidades resolvidas, exceções). O número da linha continua sendo o da planilha original mesmo após remoções.
- **Estados**: Analisada → Em tratamento → Com pendências → **Pronta para EDA** → EDA gerada. "Pronta" = nenhuma inconsistência pendente (as aceitas como exceção
  ficam registradas). O DataCheck **não** declara a base livre de problemas além das regras executadas.
- **Baixar base tratada**: CSV (delimitador, codificação e formato decimal configuráveis) ou XLSX (números/datas tipados, identificadores como texto com zeros à esquerda,
  aba opcional "Resumo do tratamento"). Textos que parecem fórmulas recebem apóstrofo.

## Análise exploratória (EDA)

Gerada pelo **Histórico → Gerar EDA** (habilitado só quando a análise está *Pronta para EDA*; senão a tela explica: "Conclua o tratamento dos dados antes de gerar a
análise exploratória") ou pelo painel de tratamento. Os relatórios ficam na página exclusiva **EDA**, separada do histórico de qualidade.

- **Configuração**: nome, versão dos dados, seções (resumo, descritivas, frequências, distribuições, correlação, valores extremos, temporal, ausentes remanescentes,
  gráficos, tratamento), colunas, Pearson/Spearman, percentis e agrupamento temporal (dia/mês/ano). Seções incompatíveis com o tipo da variável ficam desabilitadas com o motivo
  (ex.: não se calcula média de variável nominal; identificadores não entram em correlações).
- **Cálculos (Pandas/NumPy/SciPy)**: n válido/ausente, média, mediana, moda, mín/máx, amplitude, variância, desvio, CV, Q1/Q3, IIQ, percentis, assimetria, curtose;
  frequências absoluta/relativa (respeitando a ordem de ordinais); histograma, boxplot, densidade (n ≥ 30), dispersão; matriz de correlação com **n por par**;
  períodos sem registros. Trata série vazia, coluna constante, amostra pequena, divisão por zero e valores não finitos.
- **Relatório**: PDF (capa, resumo executivo, qualidade e preparação, estatísticas, distribuições, relações, extremos, temporal, observações, limitações) e XLSX (abas
  Resumo, Estatísticas descritivas, Frequências, Correlações, Valores extremos, Temporal, Informações do tratamento…). O texto é descritivo e derivado dos cálculos, sem conclusões
  causais nem inferência populacional.
- **Versão fixa**: cada EDA fica associada à versão tratada usada. Mudar os dados depois **não** altera relatórios antigos; para analisar a nova versão, gere uma nova EDA.
- **Processamento**: em segundo plano (status *na fila / gerando / concluído / falhou*, consultável); falhas não expõem dados.

## Regras de validação (`app/validators/`)

| Regra | O que verifica |
|---|---|
| A · Valores ausentes | Vazios, só espaços, marcadores configuráveis (N/A, NULL…); colunas obrigatórias (críticas); contagem e % por coluna |
| B · Duplicados | Linha completa ou colunas-chave; **todos** os registros do grupo são apontados; nada é excluído |
| C · Tipos | Inteiro, decimal, texto, data; separador decimal e formato de data configuráveis (textos numéricos válidos conforme a configuração não são erro) |
| D · Limites | Mínimo/máximo explícitos = inconsistência **confirmada** (crítica); detecção estatística opcional (IQR) = apenas **suspeito** (informativa) |
| E · Coordenadas | Latitude −90..90, longitude −180..180, ausentes, não numéricas. Ponto de extensão para regiões em `validators/geo.py` |
| F · Datas | Inexistentes (30/02), formato, intervalo mín/máx, futuras (opcional) |

Os números das linhas correspondem à planilha original (cabeçalho = linha 1). Uma célula pode ser citada por mais de
uma regra (as regras são independentes); o score usa linhas distintas.

### DataCheck Score

`Score = 100 × (1 − linhas distintas afetadas ÷ total de linhas)` — a união das linhas afetadas pelas regras
ativas, sem contar a mesma linha duas vezes; base vazia não gera nota (sem divisão por zero). Representa somente a
cobertura das regras executadas, e não garante que os dados estejam corretos (a interface exibe esse aviso).

### Insights

`services/insights.py` gera comentários e recomendações por **regras programadas**. A interface `InsightProvider`
permite plugar um modelo de linguagem no futuro (recebendo só agregados e nomes de colunas, com consentimento
explícito). Hoje não existe integração de IA generativa, e a interface não finge que existe.

## Segurança e privacidade

- **Login opcional.** Sem conta, o uso é como *visitante*: todos os visitantes compartilham o mesmo espaço e veem as análises uns dos outros. Quem cria conta (senha com **Argon2**, sessão em cookie **HttpOnly** + SameSite) tem análises privadas, invisíveis para visitantes e outras contas (recurso alheio responde 404; coberto por testes). Análises feitas como visitante não migram para a conta.
- Limite de tamanho no upload, validação de extensão/zip, proteção contra «zip bomb», XLSX lido com
  `data_only=True` (fórmulas nunca são executadas).
- Exportações neutralizam texto iniciado por `= + - @` (injeção de fórmula).
- **Base armazenada (novo)**: para permitir tratamento e EDA, o DataCheck pode guardar uma cópia privada e versionada da planilha (diretório 0700, arquivos 0600, nomes derivados de UUID; o PostgreSQL guarda só metadados e referências). É uma escolha do usuário (*Manter a base armazenada*, por análise e como preferência; ligada por padrão) e pode ser desligada. A cópia é apagada ao excluir a análise e expira após `DATA_RETENTION_DAYS`. Relatórios EDA ficam até serem excluídos; contêm estatísticas e categorias da base.
- O arquivo original enviado nunca é sobrescrito; o valor da célula só é gravado nas ocorrências se o usuário permitir (*Armazenar valores
  originais*, por análise e como preferência) — minimização de dados (LGPD). Excluir uma análise apaga as ocorrências.
- Logs não registram dados de planilhas ou pessoais; erros inesperados retornam mensagem genérica.
- Nenhum dado é enviado a serviços externos.
- Limitações conhecidas: sem limitação de taxa nem recuperação de senha; o logout apaga o cookie, mas o token assinado não é revogado no servidor antes de expirar (7 dias). Como visitante, não há privacidade entre pessoas: não exponha na internet sem restrição de acesso.

## Testes

```bash
cd datacheck_back && pytest
```

84 testes (SQLite temporário): arquivos vazios/corrompidos, nulos, duplicidades, tipos, coordenadas, datas, limites,
contagem de ocorrências × linhas afetadas, score, visitante sem login, cadastro/login/logout, **isolamento entre conta, outra conta e visitante**, fluxo completo da API, **imputação (média, mediana, moda, grupo, interpolação, qualitativas), classificação de variáveis, duplicidades, versões/desfazer, exportação da base tratada, bloqueio e geração de EDA, estatísticas descritivas e correlações conferidas contra valores calculados à mão, associação da EDA à versão**,
exportação, limpeza de temporários e cascata de exclusão. Para cada base de exemplo, o teste compara as ocorrências
detectadas com o **gabarito** (`gabarito_erros_1.csv` / `_2.csv`): nenhum erro faltando, nenhum falso positivo.
A migração do Alembic foi aplicada e conferida (`alembic check`) em PostgreSQL 16 real.

## Dados de demonstração

`datacheck_back/data/sample/`: `municipios_exemplo_1.csv` (vírgula, datas AAAA-MM-DD, ponto decimal) e
`municipios_exemplo_2.csv` (`;`, DD/MM/AAAA, vírgula decimal), cada um com 100 registros fictícios e erros propositais,
mais os gabaritos com linha, coluna e categoria esperada. Para reproduzir o gabarito: tipo *inteiro* em *Quantidade de
famílias*, limites 0–100000, latitude/longitude, datas (futuras inválidas, mínimo 1990-01-01) e, na base 2,
separador decimal *vírgula* e formato DD/MM/AAAA. Regerar: `python data/sample/generate_sample.py`.

## Validação acadêmica

`docs/VALIDACAO.md` traz o modelo (problema, hipóteses, Lean Canvas, experimento, indicadores, evidências, decisão).
O formulário **Dar feedback** (página de resultados) grava facilidade, utilidade, intenção de reuso, dificuldades e
sugestões de usuários reais; exporte com `python -m app.scripts.export_feedback > feedbacks.csv`. Nenhum feedback é gerado
artificialmente. O feedback sobrevive à exclusão da análise.

## Publicação

Backend: qualquer host de contêiner/VM com PostgreSQL gerenciado — defina `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT=production`, `COOKIE_SECURE=true` e `CORS_ORIGINS`, **restrinja o acesso de visitantes** se não quiser dados compartilhados, rode `alembic upgrade head` e
`uvicorn app.main:app --host 0.0.0.0`. Frontend: `npm run build` gera `dist/` (hospedagem estática). Sirva front e API
sob o mesmo domínio (proxy reverso `/api`) ou ajuste `VITE_API_URL`, CORS e SameSite. Não testado em ambiente de produção.

## Próximos passos

PDF do relatório completo de qualidade (hoje só a tabela de inconsistências), EDA em HTML, comparações entre grupos na EDA, fila de tarefas externa (hoje `BackgroundTasks` no mesmo processo), validação por região geográfica, regras personalizadas, recuperação de senha, limitação de taxa,
provedor de LLM opcional e testes de interface (Vitest/Playwright).
