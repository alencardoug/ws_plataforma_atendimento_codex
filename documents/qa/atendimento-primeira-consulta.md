# Atendimento à primeira consulta — Q&A

Referência Oncológica Cancer Center. Todas as informações institucionais, profissionais, comerciais, telefônicas, de agenda e pagamento são simulação.

## O que é a Referência Oncológica Cancer Center?

É uma instituição oncológica fictícia criada para esta demonstração. O atendimento simulado integra avaliação médica, cirurgia, quimioterapia, radioterapia, exames, reabilitação e apoio emocional.

`qa_id: QA-001` · `categoria: instituicao`

## Por que escolher a instituição para a primeira consulta?

A proposta simulada é concentrar especialistas e serviços oncológicos em uma jornada coordenada, com possibilidade de revisão de exames e discussão multidisciplinar. A indicação individual depende da consulta.

`qa_id: QA-002` · `categoria: instituicao`

## A instituição trata câncer de mama?

Sim. A instituição informa oferecer mastologia, cirurgia oncológica, oncologia clínica, radioterapia, reconstrução, fisioterapia, psicologia e exames relacionados (simulação).

`qa_id: QA-003` · `categoria: instituicao`

## A instituição trata câncer colorretal?

Sim. A jornada simulada inclui cirurgia colorretal, oncologia clínica, radioterapia para situações indicadas, endoscopia, estomaterapia, nutrição, psicologia e reabilitação.

`qa_id: QA-004` · `categoria: instituicao`

## Existe tumor board?

Sim. Casos selecionados podem ser discutidos por uma equipe multidisciplinar, chamada tumor board (simulação). A discussão não é automática nem substitui a conversa do paciente com o médico responsável.

`qa_id: QA-005` · `categoria: instituicao`

## Posso fazer todo o tratamento no mesmo lugar?

A instituição informa dispor de consultas, exames, cirurgia, infusão, radioterapia e apoio multiprofissional (simulação). Depois da avaliação, a equipe explica quais etapas podem ser realizadas localmente.

`qa_id: QA-006` · `categoria: instituicao`

## Vocês oferecem psicologia?

Sim. Contamos com apoio psicológico e psico-oncológico, que pode ser solicitado pelo paciente ou familiar em diferentes fases do cuidado (simulação).

`qa_id: QA-007` · `categoria: instituicao`

## Existe atendimento de nutrição?

Sim. A nutrição oncológica pode orientar alimentação durante cirurgia, quimioterapia, radioterapia e adaptação intestinal ou à estomia (simulação).

`qa_id: QA-008` · `categoria: instituicao`

## Há fisioterapia e reabilitação?

Sim. A oferta simulada inclui reabilitação após cirurgia da mama, prevenção e manejo de linfedema, mobilidade e recuperação após cirurgia abdominal ou pélvica.

`qa_id: QA-009` · `categoria: instituicao`

## A instituição oferece cuidados com estomia?

Sim. A estomaterapia orienta escolha e troca de bolsa, proteção da pele, hidratação e adaptação à ileostomia ou colostomia (simulação).

`qa_id: QA-010` · `categoria: instituicao`

## Quero marcar minha primeira consulta. Como faço?

Informe a especialidade desejada, nome, contato e preferência de período. O CPF será solicitado somente na reserva. O chatbot consulta `scheduling.available_offers`: apresenta até quatro vagas por especialidade para o próximo dia útil e até quatro para o primeiro dia útil em D+7, sempre em `America/Sao_Paulo` e com indicação “(simulação)”.

`qa_id: QA-011` · `categoria: agenda`

## Existe consulta disponível amanhã?

O chatbot consulta `scheduling.available_offers`: apresenta até quatro vagas por especialidade para o próximo dia útil e até quatro para o primeiro dia útil em D+7, sempre em `America/Sao_Paulo` e com indicação “(simulação)”.

`qa_id: QA-012` · `categoria: agenda`

## Existe consulta disponível na semana que vem?

O chatbot consulta `scheduling.available_offers`: apresenta até quatro vagas por especialidade para o próximo dia útil e até quatro para o primeiro dia útil em D+7, sempre em `America/Sao_Paulo` e com indicação “(simulação)”.

`qa_id: QA-013` · `categoria: agenda`

## Quantos horários o chatbot oferece?

São oferecidas no máximo quatro vagas por especialidade em cada janela dinâmica: próximo dia útil e primeiro dia útil calculado a partir de D+7 (simulação).

`qa_id: QA-014` · `categoria: agenda`

## O que acontece se amanhã for domingo ou feriado?

A aplicação consulta `scheduling.holidays` e move a oferta para o próximo dia útil. Sábados podem ter atendimento das 8h às 12h; domingos ficam bloqueados (simulação).

`qa_id: QA-015` · `categoria: agenda`

## A agenda exibida fica reservada para mim?

Não apenas por ser exibida. Depois que você escolhe e envia os dados, a vaga fica retida por 30 minutos (simulação). Se o fluxo não for concluído, ela pode voltar a ficar disponível.

`qa_id: QA-016` · `categoria: agenda`

## Posso escolher um profissional?

Sim, quando houver vaga. A busca pode filtrar profissional, especialidade, data e período. Se não houver o nome desejado, o chatbot apresenta outros especialistas da mesma jornada (simulação).

`qa_id: QA-017` · `categoria: agenda`

## Posso escolher manhã ou tarde?

Sim. Informe a preferência e a aplicação filtrará as vagas dinâmicas. Aos sábados, a agenda simulada funciona apenas pela manhã.

`qa_id: QA-018` · `categoria: agenda`

## Vocês atendem aos sábados?

Sim, há agenda simulada aos sábados entre 8h e 12h. A disponibilidade deve ser confirmada no PostgreSQL.

`qa_id: QA-019` · `categoria: agenda`

## Vocês atendem aos domingos?

A agenda eletiva simulada não abre aos domingos. Se a data calculada cair no domingo, será usado o próximo dia útil.

`qa_id: QA-020` · `categoria: agenda`

## Posso agendar para outra pessoa?

Sim, desde que você tenha autorização para informar os dados dela. O CPF, o consentimento e os dados clínicos devem pertencer ao paciente, não ao acompanhante.

`qa_id: QA-021` · `categoria: agenda`

## Menor de idade pode ser agendado?

Sim, com dados do paciente e identificação do responsável legal. O fluxo deve coletar o vínculo do responsável e aplicar consentimento apropriado; este cenário requer atendimento assistido (simulação).

`qa_id: QA-022` · `categoria: agenda`

## Como recebo a confirmação?

Após a confirmação simulada do pagamento, o chatbot exibe profissional, data, horário, unidade, valor, protocolo e políticas. Também pode enviar confirmação no Telegram ou na sessão web.

`qa_id: QA-023` · `categoria: agenda`

## Perdi meu protocolo. O que faço?

Use o CPF e um segundo fator de verificação pelo canal seguro para localizar o agendamento. O chatbot não deve revelar agenda apenas com nome ou CPF digitado.

`qa_id: QA-024` · `categoria: agenda`

## Quanto custa uma consulta de mastologia?

O valor fixo é consultado na tabela `scheduling.professional_specialties` e deve ser exibido com “(simulação)”. A aplicação nunca deve responder com um preço memorizado pelo vetor.

`qa_id: QA-025` · `categoria: preco`

## Quanto custa uma consulta colorretal?

O valor fixo é consultado na tabela `scheduling.professional_specialties` e deve ser exibido com “(simulação)”. A aplicação nunca deve responder com um preço memorizado pelo vetor.

`qa_id: QA-026` · `categoria: preco`

## Quanto custa uma segunda opinião?

O valor fixo é consultado na tabela `scheduling.professional_specialties` e deve ser exibido com “(simulação)”. A aplicação nunca deve responder com um preço memorizado pelo vetor.

`qa_id: QA-027` · `categoria: preco`

## O preço muda conforme o horário?

Na simulação, o preço é fixo por combinação de profissional e especialidade e não muda pela janela D+1 ou D+7. A aplicação confirma o valor antes de solicitar CPF.

`qa_id: QA-028` · `categoria: preco`

## O valor inclui exames?

Não. O preço exibido corresponde somente ao tipo de consulta informado, salvo indicação expressa em contrário (simulação). Exames e procedimentos devem ter orçamento separado.

`qa_id: QA-029` · `categoria: preco`

## Posso pagar depois da consulta?

No fluxo simulado, o pagamento é solicitado para concluir a reserva. O link fictício é exibido e a confirmação simulada ocorre após três segundos.

`qa_id: QA-030` · `categoria: preco`

## Como faço o pagamento?

O chatbot mostra `www.pagamento_fictico.cancercenter.com` (simulação). O endereço é propositalmente não funcional; após três segundos, o ambiente registra “Pagamento confirmado (simulação)”.

`qa_id: QA-031` · `categoria: pagamento`

## O link de pagamento não abriu. O que faço?

Neste protótipo, isso é esperado: o link é fictício e quebrado. Aguarde a mensagem automática de confirmação simulada. Não informe cartão, senha ou código de segurança.

`qa_id: QA-032` · `categoria: pagamento`

## É seguro enviar dados do cartão no chat?

Não. Nunca envie número completo do cartão, senha ou código de segurança pelo chatbot. O protótipo não coleta dados reais de pagamento.

`qa_id: QA-033` · `categoria: pagamento`

## Receberei comprovante?

Sim. A confirmação simulada informa valor, protocolo e horário do evento. Ela não é comprovante fiscal nem confirma transação financeira real.

`qa_id: QA-034` · `categoria: pagamento`

## Vocês atendem convênio?

O chatbot pode consultar uma tabela simulada de convênios e planos. Cobertura, autorização e coparticipação devem ser confirmadas antes do atendimento; ter o nome da operadora não garante cobertura.

`qa_id: QA-035` · `categoria: convenio`

## Meu convênio não aparece. Posso marcar particular?

Sim. Você pode escolher atendimento particular com preço fixo simulado e depois verificar eventual reembolso diretamente com a operadora.

`qa_id: QA-036` · `categoria: convenio`

## Vocês fornecem documento para reembolso?

A instituição pode fornecer recibo ou documentação do atendimento particular conforme o serviço realizado (simulação). A operadora decide cobertura e valor de reembolso.

`qa_id: QA-037` · `categoria: convenio`

## Posso ser atendido pelo SUS?

O protótipo pode explicar jornadas pública e particular, mas não promete vaga ou encaminhamento pelo SUS. Para acesso público, confirme os fluxos oficiais da rede de saúde da sua região.

`qa_id: QA-038` · `categoria: sus`

## Moro em outro estado. Posso consultar?

Sim. Antes da viagem, o atendimento pode orientar quais exames levar e se a primeira avaliação pode começar remotamente, quando permitido (simulação). Procedimentos presenciais exigem planejamento próprio.

`qa_id: QA-039` · `categoria: outro_estado`

## Como funciona a segunda opinião?

Um especialista revisa história, laudos, imagens disponíveis e proposta terapêutica (simulação). A conclusão pode depender de revisão anatomopatológica ou de exames adicionais.

`qa_id: QA-040` · `categoria: segunda_opiniao`

## O que levar à primeira consulta?

Leve documento de identificação, lista de medicamentos e alergias, laudos, imagens em formato acessível, biópsia, relatório de cirurgias e contato dos médicos anteriores. Não adie a consulta apenas porque falta algum item.

`qa_id: QA-041` · `categoria: preparo`

## Preciso levar as imagens ou só o laudo?

Quando possível, leve ambos. O laudo resume achados, mas as imagens podem ser necessárias para segunda opinião e planejamento.

`qa_id: QA-042` · `categoria: preparo`

## Preciso estar em jejum para a consulta?

Em geral, consulta não exige jejum. Se houver exame ou procedimento no mesmo dia, siga a instrução específica enviada pela equipe.

`qa_id: QA-043` · `categoria: preparo`

## Posso levar acompanhante?

Sim. Um acompanhante pode ajudar a lembrar informações e fazer perguntas (simulação). O paciente decide o que pode ser compartilhado, salvo situações legais específicas.

`qa_id: QA-044` · `categoria: preparo`

## Posso gravar a consulta?

Pergunte ao profissional antes de gravar. Uma alternativa é levar perguntas escritas e pedir um resumo do plano. Respeite a privacidade de outras pessoas e da equipe.

`qa_id: QA-045` · `categoria: preparo`

## Ainda não tenho biópsia. Posso consultar?

Sim. A consulta pode organizar a investigação. O médico avaliará quais exames são realmente necessários e em que ordem.

`qa_id: QA-046` · `categoria: preparo`

## Meu diagnóstico acabou de sair. Qual especialidade escolho?

Para alteração mamária, escolha mastologia oncológica; para cólon ou reto, cirurgia colorretal oncológica. Se ainda houver dúvida, o fluxo de navegação pode encaminhar para triagem humana (simulação).

`qa_id: QA-047` · `categoria: preparo`

## Há quimioterapia no local?

Sim. A instituição informa possuir centro de infusão para quimioterapia e outros tratamentos sistêmicos (simulação). A primeira consulta define indicação, protocolo e exames necessários.

`qa_id: QA-048` · `categoria: servicos`

## Há radioterapia no local?

Sim. A Referência Oncológica Cancer Center informa oferecer planejamento e aplicação de radioterapia (simulação). A indicação depende do tipo, localização e fase do câncer.

`qa_id: QA-049` · `categoria: servicos`

## Posso fazer exames de imagem no local?

A instituição informa oferecer estrutura diagnóstica e exames de imagem selecionados (simulação). A disponibilidade e o preparo devem ser consultados por tipo de exame.

`qa_id: QA-050` · `categoria: servicos`

## Vocês revisam lâminas de biópsia?

A revisão anatomopatológica pode ser solicitada em casos selecionados (simulação). A equipe informa como transportar lâminas, blocos e laudos com segurança.

`qa_id: QA-051` · `categoria: servicos`

## A radioterapia dói?

A aplicação externa geralmente não causa dor no momento em que a radiação é entregue, mas efeitos na pele, cansaço ou sintomas da região tratada podem surgir ao longo das sessões. Avise a equipe cedo.

`qa_id: QA-052` · `categoria: servicos`

## A quimioterapia sempre causa queda de cabelo?

Não. O risco depende dos medicamentos e doses. A equipe explicará os efeitos mais prováveis do protocolo individual; não compare tratamentos apenas pelo nome câncer.

`qa_id: QA-053` · `categoria: servicos`

## O que é navegação do paciente?

É o apoio para organizar etapas, documentos, encaminhamentos e comunicação ao longo da jornada (simulação). Não substitui decisões médicas.

`qa_id: QA-054` · `categoria: servicos`

## Familiares também podem receber apoio psicológico?

Sim, conforme disponibilidade e avaliação do serviço (simulação). Cuidadores também podem precisar de orientação e espaço de escuta.

`qa_id: QA-055` · `categoria: servicos`

## A instituição tem pronto-socorro?

A instituição informa dispor de atendimento para intercorrências oncológicas (simulação), mas não deve ser forçada como destino. Se houver falta de ar importante, desmaio, confusão, dor forte no peito, sangramento volumoso ou piora rápida, procure o serviço de emergência mais próximo. Não espere resposta do chatbot. Para dúvida não emergencial, Ramal 0000 (simulação).

`qa_id: QA-056` · `categoria: urgencia`

## Estou com febre durante a quimioterapia. O que faço?

Febre durante quimioterapia pode exigir avaliação rápida. Siga o limite e o telefone fornecidos pela equipe; se houver piora, calafrios intensos, confusão ou dificuldade para chegar com segurança, procure a emergência mais próxima.

`qa_id: QA-057` · `categoria: urgencia`

## A ferida cirúrgica está vermelha. É emergência?

Vermelhidão pequena e estável pode ter causas diferentes, mas aumento, calor, pus, febre, abertura ou dor crescente exigem contato no mesmo dia. Piora rápida ou estado geral ruim exige emergência próxima.

`qa_id: QA-058` · `categoria: urgencia`

## Estou com falta de ar. Posso esperar a central responder?

Se houver falta de ar importante, desmaio, confusão, dor forte no peito, sangramento volumoso ou piora rápida, procure o serviço de emergência mais próximo. Não espere resposta do chatbot. Para dúvida não emergencial, Ramal 0000 (simulação).

`qa_id: QA-059` · `categoria: urgencia`

## O chatbot faz diagnóstico?

Não. Ele oferece informação educativa, ajuda a organizar atendimento e reconhece sinais de alerta. Diagnóstico, prescrição e mudança de tratamento exigem profissional habilitado.

`qa_id: QA-060` · `categoria: urgencia`

## Por que vocês pedem CPF?

O CPF é solicitado na etapa de reserva para identificar o paciente, evitar duplicidade e vincular o agendamento (simulação). Ele não deve ser colocado em embeddings, URLs ou mensagens abertas.

`qa_id: QA-061` · `categoria: privacidade`

## Meu CPF ficará salvo?

Sim, no protótipo ele é armazenado cifrado, acompanhado de hash para evitar duplicidade e últimos dígitos para conferência. A chave de demonstração deve ser substituída em qualquer ambiente real.

`qa_id: QA-062` · `categoria: privacidade`

## Posso enviar meus laudos pelo Telegram?

Evite enviar documentos de saúde por canal não aprovado. O chatbot deve direcionar para um upload seguro com controle de acesso, prazo de retenção e confirmação de finalidade.

`qa_id: QA-063` · `categoria: privacidade`

## Quais dados serão coletados?

Nome, CPF na reserva, telefone, e-mail, dados básicos de contato, convênio, motivo da consulta, preferência de horário e consentimento. Colete somente o necessário para a etapa atual.

`qa_id: QA-064` · `categoria: privacidade`

## Como peço correção ou exclusão dos meus dados?

Use o canal de privacidade ou Ramal 0000 (simulação). A instituição deve confirmar identidade e avaliar obrigações legais de guarda antes de corrigir ou eliminar informações.

`qa_id: QA-065` · `categoria: privacidade`

## Como reagendo minha consulta?

Solicite pelo chatbot ou Ramal 0000 (simulação). Reagendamento sem custo é oferecido até 24 horas antes, sujeito à nova disponibilidade e à versão vigente da política simulada.

`qa_id: QA-066` · `categoria: cancelamento`

## Como cancelo minha consulta?

O cancelamento pode ser solicitado pelo mesmo canal do agendamento ou pelo Ramal 0000 (simulação). O sistema informa protocolo, situação do pagamento e eventual devolução.

`qa_id: QA-067` · `categoria: cancelamento`

## O que acontece se eu faltar?

Na política simulada, falta sem cancelamento gera retenção de 30% e devolução de 70% do valor pago. Direitos previstos na legislação aplicável continuam preservados.

`qa_id: QA-068` · `categoria: cancelamento`

## E se a instituição cancelar?

Você poderá escolher outro horário ou solicitar devolução integral do valor pago (simulação). A alteração será registrada e comunicada pelo canal escolhido.

`qa_id: QA-069` · `categoria: cancelamento`

## Tenho direito de arrependimento?

Contratações online estão sujeitas às regras aplicáveis do Código de Defesa do Consumidor, incluindo o art. 49 quando cabível. O chatbot não reduz esse direito e encaminha casos duvidosos para atendimento humano.

`qa_id: QA-070` · `categoria: cancelamento`

## Quanto tempo demora o estorno?

A solicitação é registrada imediatamente, mas o prazo de crédito depende do meio de pagamento e da instituição financeira. Como o pagamento deste protótipo é fictício, o estorno também será apenas simulado.

`qa_id: QA-071` · `categoria: cancelamento`

## Câncer de mama é hereditário? Minha mãe teve, e eu, vou ter também?

Ter um parente próximo com câncer pede atenção, mas não significa que você terá a doença: a maioria dos casos não é hereditária. Quando há vários casos na família, diagnóstico em idade jovem ou outros sinais de alerta, a equipe pode indicar aconselhamento genético para avaliar o risco individual com mais precisão.

`qa_id: QA-072` · `categoria: risco_hereditario`

## O que é aconselhamento genético e quando ele é indicado?

É uma consulta especializada que analisa o histórico familiar de câncer e, quando indicado, solicita exame genético para orientar rastreamento, prevenção e decisões de tratamento. A indicação depende de critérios clínicos avaliados por profissional habilitado; o chatbot não define essa indicação sozinho.

`qa_id: QA-073` · `categoria: risco_hereditario`

## Existe exame de sangue para saber se eu tenho um gene de risco, como BRCA?

Sim, existem exames genéticos (como para os genes BRCA1 e BRCA2) que podem ser solicitados em casos com critério clínico definido. O resultado deve ser interpretado dentro do aconselhamento genético: um exame positivo indica risco aumentado, não diagnóstico de câncer.

`qa_id: QA-074` · `categoria: risco_hereditario`

## Ter um caso de câncer na família significa que devo começar exames de rastreamento mais cedo?

Pode ser o caso, dependendo do tipo de câncer, do grau de parentesco e da idade em que o familiar foi diagnosticado. Essa decisão é individual e deve ser discutida em consulta; não existe uma regra única aplicável a todas as famílias.

`qa_id: QA-075` · `categoria: risco_hereditario`

## Não tenho dinheiro nem plano de saúde. Como posso ser tratado?

A ausência de plano ou de condição financeira não impede o acesso ao tratamento oncológico: o SUS garante atendimento gratuito, incluindo cirurgia, quimioterapia e radioterapia, pela rede pública. O primeiro passo costuma ser a Unidade Básica de Saúde (UBS) da sua região, que avalia e encaminha para uma unidade especializada quando necessário. A instituição simulada aqui não substitui essa rede.

`qa_id: QA-076` · `categoria: sus`

## Como funciona o encaminhamento para tratamento oncológico pelo SUS?

Em geral, o fluxo público começa na UBS ou no pronto atendimento, que encaminha para investigação e, se o câncer for confirmado, para uma unidade habilitada em oncologia (CACON ou UNACON). Prazos e portas de entrada variam por município e estado; confirme o fluxo vigente na secretaria de saúde local.

`qa_id: QA-077` · `categoria: sus`

## O tratamento oncológico pelo SUS demora muito? Existe fila?

Pode haver fila, e o tempo varia por região e tipo de tratamento. A Lei nº 12.732/2012 prevê prazo máximo de 60 dias entre o diagnóstico confirmado em laudo e o início do primeiro tratamento oncológico pelo SUS; se esse prazo não for cumprido, é possível buscar a ouvidoria do SUS ou a Defensoria Pública.

`qa_id: QA-078` · `categoria: sus`

## Preciso de guia, encaminhamento ou algum documento específico para buscar atendimento público?

Geralmente são pedidos cartão SUS (ou CPF, que pode gerá-lo na hora), documento de identificação e, quando houver, laudos e exames já realizados. O encaminhamento formal costuma ser produzido pela própria rede pública durante o atendimento; você não precisa consegui-lo sozinho antes de procurar ajuda.

`qa_id: QA-079` · `categoria: sus`

## Estou com muito medo desde que recebi o diagnóstico. Isso é normal?

Sim, é uma reação comum. Medo, tristeza, raiva e negação podem aparecer e mudar de intensidade ao longo do tratamento. Você não precisa passar por isso sozinho: apoio psicológico e psico-oncológico pode ajudar. Se o sofrimento for muito intenso ou houver isolamento, procure ajuda imediatamente.

`qa_id: QA-080` · `categoria: apoio_emocional`

## Tenho medo de morrer por causa do câncer. Vocês podem me ajudar com isso?

Esse medo é comum e válido, e merece espaço para ser conversado, não apenas respondido com informação técnica. A equipe de psico-oncologia pode ajudar a lidar com esse sentimento junto com o cuidado clínico. O prognóstico depende do seu caso específico e deve ser discutido com o médico responsável; nenhuma estimativa individual deve ser dada fora dessa consulta.

`qa_id: QA-081` · `categoria: apoio_emocional`

## Não consigo dormir pensando na doença. O que posso fazer?

Dificuldade para dormir é comum durante o tratamento oncológico. Rotinas de sono, conversar sobre as preocupações com a equipe e apoio psicológico podem ajudar. Se a insônia persistir, piorar o humor ou vier acompanhada de outros sintomas, converse com a equipe médica.

`qa_id: QA-082` · `categoria: apoio_emocional`

## Como conto para meus filhos que estou com câncer?

Não existe um único jeito certo; a conversa pode ser adaptada à idade e à personalidade da criança ou adolescente. Equipes de psicologia e serviço social podem ajudar a preparar essa conversa e orientar sobre como responder perguntas difíceis (simulação de disponibilidade do serviço).

`qa_id: QA-083` · `categoria: apoio_emocional`

## Estou no estágio 2, quantos anos ainda vou viver?

Não é possível nem responsável dar um número de expectativa de vida por chat. Estatísticas de sobrevida são calculadas em grandes grupos de pacientes e não preveem o resultado de uma pessoa específica: elas não consideram biomarcadores, resposta ao tratamento, comorbidades e outros fatores do seu caso. Essa conversa deve acontecer com o médico responsável, que conhece seu histórico completo, idealmente com apoio psico-oncológico junto.

`qa_id: QA-084` · `categoria: prognostico`

## Meu estágio é grave? Ainda dá tempo de tratar?

O estadiamento ajuda a planejar o tratamento, mas não é, sozinho, uma sentença sobre o resultado. A maioria dos estágios tem alguma forma de tratamento disponível. Essa avaliação depende de exames e do histórico completo, e deve ser feita pelo médico responsável; o chatbot não interpreta estadiamento nem estima prognóstico.

`qa_id: QA-085` · `categoria: prognostico`

## Posso confiar em estatísticas de sobrevida que encontrei na internet para saber o que vai acontecer comigo?

Use com cautela. Essas estatísticas descrevem grupos de pacientes no passado, muitas vezes com protocolos diferentes dos atuais, e não descrevem um caso individual. Leve a dúvida para a consulta: o médico pode explicar o que é ou não aplicável à sua situação.

`qa_id: QA-086` · `categoria: prognostico`
