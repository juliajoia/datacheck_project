# Lean Canvas — DataCheck

> **Dados confiáveis. Decisões inteligentes.**
>
> Rascunho montado a partir do que o produto faz hoje (README). Tudo sobre clientes, preços e mercado é **hipótese a validar** com usuários reais (veja `VALIDACAO.md`); nada aqui é evidência coletada.

| | |
|---|---|
| **1. Problema** | **4. Solução** |
| • Planilhas CSV/XLSX chegam com ausentes, duplicatas, tipos errados, datas inválidas e coordenadas fora do intervalo.<br>• A busca de erros é manual, demorada e não deixa registro do que foi alterado.<br>• Corrigir "no olho" ou no Excel gera retrabalho e decisões baseadas em dados ruins.<br>• Ferramentas de limpeza existentes são técnicas (código) ou não explicam por que sugerem uma correção.<br><br>**Alternativas atuais:** Excel/Google Sheets, scripts Pandas/R, OpenRefine, ferramentas de BI. | • Diagnóstico automático com 6 regras configuráveis (ausentes, duplicados, tipos, limites, coordenadas, datas) e **DataCheck Score**.<br>• Tratamento guiado com sugestões explicáveis: prévia → confirmação → nova versão imutável, com histórico, desfazer e restauração.<br>• Exportação da base tratada (CSV/XLSX).<br>• Relatório de análise exploratória (EDA) em PDF/XLSX, fixado na versão dos dados usada.<br>• Uso como visitante, login opcional. |
| **2. Segmentos de clientes** | **3. Proposta de valor única** |
| • Estudantes e pesquisadores que trabalham com bases de dados.<br>• Analistas de dados/BI iniciantes ou de equipes pequenas.<br>• Profissionais administrativos e de órgãos públicos que consolidam planilhas (ex.: dados de municípios).<br><br>**Early adopters (hipótese):** pesquisadores e estudantes com planilhas reais e pouca familiaridade com programação. | **Da planilha suja ao relatório exploratório, sem escrever código — e com cada decisão explicada e registrada.**<br><br>Diferenciais: nada é aplicado sem confirmação, a base original nunca é sobrescrita, o app não declara a base "livre de erros" além das regras executadas.<br><br>**Conceito de alto nível:** "um assistente de qualidade de dados para quem não programa". |
| **8. Canais** | **9. Vantagem competitiva** |
| • Divulgação em universidades, grupos de pesquisa e disciplinas de estatística/dados.<br>• Comunidades de dados abertos e de BI.<br>• Conteúdo educativo (como limpar uma planilha, uso das bases de demonstração).<br>• Indicação boca a boca a partir do relatório EDA compartilhado. | • Ciclo completo em um só lugar (diagnóstico → tratamento → validação → EDA).<br>• Explicabilidade e rastreabilidade: histórico de correções com antes/depois, método e justificativa.<br>• Tipos estatísticos das variáveis (CPF, CEP, IDs não viram "número").<br>• Privacidade: sem envio a serviços externos, valores originais só armazenados com consentimento (LGPD), retenção configurável.<br>• Validado contra gabarito: 84 testes, sem falsos positivos nas bases de exemplo. |
| **7. Métricas-chave** | **5. Fontes de receita** |
| • Facilidade de uso (1–5), meta média ≥ 4.<br>• Utilidade percebida (1–5), meta média ≥ 4.<br>• Intenção de reuso ≥ 60% "sim".<br>• Taxa de conclusão da tarefa ≥ 80%.<br>• Erros do gabarito encontrados ≥ 80%.<br>• Análises concluídas até "Pronta para EDA"; EDAs geradas por usuário.<br>• Mínimo de 5 usuários reais na validação acadêmica. | *Hipóteses, nenhuma testada:*<br>• Plano gratuito com limite de tamanho/quantidade de análises (hoje 10 MB por arquivo).<br>• Plano pago para equipes: contas privadas, mais volume, retenção maior, regras personalizadas.<br>• Licença institucional para universidades e órgãos públicos.<br>• Fase atual: projeto acadêmico, sem receita. |
| **6. Estrutura de custos** | |
| • Hospedagem do backend e PostgreSQL gerenciado; armazenamento das bases e relatórios.<br>• Processamento (Pandas/EDA em segundo plano; hoje no mesmo processo, sem fila externa).<br>• Tempo de desenvolvimento e manutenção (front React, back FastAPI).<br>• Segurança e conformidade (LGPD, limitação de taxa, recuperação de senha, ainda pendentes).<br>• Suporte e produção de conteúdo. | |

## Riscos e hipóteses mais críticas

1. **Problema:** o público-alvo realmente sente dor suficiente para trocar Excel/scripts por uma ferramenta nova? (testar em entrevista, meta ≥ 4 de 5.)
2. **Confiança:** usuários confiam nas sugestões de tratamento (imputação, duplicatas) mesmo com o aviso de que são heurísticas?
3. **Receita:** há disposição a pagar, ou o valor é só acadêmico/educacional?
4. **Privacidade:** enviar planilhas a um serviço web é aceitável para órgãos e empresas, ou exigiria versão local/auto-hospedada?

## Lacunas atuais do produto que afetam o modelo

Sem limitação de taxa nem recuperação de senha; visitantes compartilham o mesmo espaço (não expor publicamente sem restrição); fila de tarefas externa, regras personalizadas, validação por região e provedor de LLM opcional são próximos passos.
