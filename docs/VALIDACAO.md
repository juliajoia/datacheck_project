# Validação do produto — modelo de documentação

Este arquivo é um **modelo em branco** para o projeto de Metodologias Ágeis e Validação de Produtos.
Nada aqui foi preenchido com dados inventados: as evidências devem vir de participantes reais.

## 1. Problema identificado
- Quem tem o problema? Em que situação?
- Como resolve hoje? Qual o custo (tempo, retrabalho, decisões erradas)?

## 2. Público-alvo e segmento inicial
- Perfis (analistas/BI, pesquisadores, estudantes, administrativos, organizações):
- Early adopters escolhidos:

## 3. Hipóteses
| Tipo | Hipótese | Como será testada | Critério de sucesso |
|---|---|---|---|
| Problema | Ex.: «Pessoas que usam planilhas perdem tempo procurando erros manualmente.» | Entrevista / pergunta no teste | ≥ 4 de 5 confirmam |
| Solução | Ex.: «Um diagnóstico automático encontra erros que passariam despercebidos.» | Tarefa com a base de demonstração | Encontram ≥ 80% dos erros do gabarito |
| Valor | Ex.: «Usariam novamente / recomendariam.» | Formulário de feedback | ≥ 60% respondem «sim» |

## 4. Lean Canvas
Problema · Segmentos de clientes · Proposta de valor única · Solução · Canais · Fontes de receita ·
Estrutura de custos · Métricas-chave · Vantagem competitiva (preencher).

## 5. Experimento
- Participantes: **mínimo de 5 usuários reais** (registre perfil, sem dados pessoais sensíveis).
- Tarefa sugerida: carregar `datacheck_back/data/sample/municipios_exemplo_1.csv` (ou `_2`),
  configurar as regras e identificar os erros. O gabarito está em `gabarito_erros_1.csv` / `_2.csv`.
- Também vale testar com a planilha real do participante (só se ele consentir).
- Procedimento: observar sem ajudar; anotar tempo, dúvidas e erros de interpretação.
- O login é opcional. Como visitantes compartilham o histórico, anote quem fez cada análise na ficha de observação (ou peça que cada participante crie a própria conta). Após a análise, cada um usa **Dar feedback** na página de resultados.

- Para testar o ciclo completo: diagnóstico → **Tratar dados** (imputar, remover duplicatas, aceitar exceções) → **Gerar EDA** pelo Histórico → conferir o relatório na página **EDA**. Registre se o participante entendeu as recomendações de tratamento e se confiou nelas.

## 6. Indicadores e critérios de sucesso
| Indicador | Fonte | Meta |
|---|---|---|
| Facilidade de uso (1–5) | Feedback | média ≥ 4 |
| Utilidade percebida (1–5) | Feedback | média ≥ 4 |
| Intenção de reutilizar | Feedback | ≥ 60% «sim» |
| Taxa de conclusão da tarefa | Observação | ≥ 80% |
| Erros do gabarito encontrados | Resultado da análise × gabarito | ≥ 80% |

## 7. Evidências coletadas
Os feedbacks ficam na tabela `analysis_feedback`. Para exportar (sem identificar usuários):

```bash
cd datacheck_back
python -m app.scripts.export_feedback > feedbacks.csv
```

Anexe aqui: o CSV exportado, anotações de observação e capturas de tela (anonimizadas).

## 8. Resultados e aprendizados
- O que confirmou as hipóteses? O que as refutou? O que surpreendeu?

## 9. Decisão final
☐ Perseverar  ☐ Ajustar  ☐ Pivotar  ☐ Abandonar — justificativa baseada nas evidências acima.
