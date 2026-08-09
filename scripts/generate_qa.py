"""Gera Q&A independente, sem relação parent-child."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRICE = "O valor fixo é consultado na tabela `scheduling.professional_specialties` e deve ser exibido com “(simulação)”. A aplicação nunca deve responder com um preço memorizado pelo vetor."
SCHEDULE = "O chatbot consulta `scheduling.available_offers`: apresenta até quatro vagas por especialidade para o próximo dia útil e até quatro para o primeiro dia útil em D+7, sempre em `America/Sao_Paulo` e com indicação “(simulação)”."
EMERGENCY = "Se houver falta de ar importante, desmaio, confusão, dor forte no peito, sangramento volumoso ou piora rápida, procure o serviço de emergência mais próximo. Não espere resposta do chatbot. Para dúvida não emergencial, Ramal 0000 (simulação)."

QA = [
    ("instituicao","O que é a Referência Oncológica Cancer Center?","É uma instituição oncológica fictícia criada para esta demonstração. O atendimento simulado integra avaliação médica, cirurgia, quimioterapia, radioterapia, exames, reabilitação e apoio emocional."),
    ("instituicao","Por que escolher a instituição para a primeira consulta?","A proposta simulada é concentrar especialistas e serviços oncológicos em uma jornada coordenada, com possibilidade de revisão de exames e discussão multidisciplinar. A indicação individual depende da consulta."),
    ("instituicao","A instituição trata câncer de mama?","Sim. A instituição informa oferecer mastologia, cirurgia oncológica, oncologia clínica, radioterapia, reconstrução, fisioterapia, psicologia e exames relacionados (simulação)."),
    ("instituicao","A instituição trata câncer colorretal?","Sim. A jornada simulada inclui cirurgia colorretal, oncologia clínica, radioterapia para situações indicadas, endoscopia, estomaterapia, nutrição, psicologia e reabilitação."),
    ("instituicao","Existe tumor board?","Sim. Casos selecionados podem ser discutidos por uma equipe multidisciplinar, chamada tumor board (simulação). A discussão não é automática nem substitui a conversa do paciente com o médico responsável."),
    ("instituicao","Posso fazer todo o tratamento no mesmo lugar?","A instituição informa dispor de consultas, exames, cirurgia, infusão, radioterapia e apoio multiprofissional (simulação). Depois da avaliação, a equipe explica quais etapas podem ser realizadas localmente."),
    ("instituicao","Vocês oferecem psicologia?","Sim. O apoio psicológico pode ser solicitado pelo paciente ou familiar em diferentes fases do cuidado (simulação). Em risco imediato de autoagressão, procure emergência e não aguarde agendamento comum."),
    ("instituicao","Existe atendimento de nutrição?","Sim. A nutrição oncológica pode orientar alimentação durante cirurgia, quimioterapia, radioterapia e adaptação intestinal ou à estomia (simulação)."),
    ("instituicao","Há fisioterapia e reabilitação?","Sim. A oferta simulada inclui reabilitação após cirurgia da mama, prevenção e manejo de linfedema, mobilidade e recuperação após cirurgia abdominal ou pélvica."),
    ("instituicao","A instituição oferece cuidados com estomia?","Sim. A estomaterapia orienta escolha e troca de bolsa, proteção da pele, hidratação e adaptação à ileostomia ou colostomia (simulação)."),
    ("agenda","Quero marcar minha primeira consulta. Como faço?",f"Informe a especialidade desejada, nome, contato e preferência de período. O CPF será solicitado somente na reserva. {SCHEDULE}"),
    ("agenda","Existe consulta disponível amanhã?",SCHEDULE),
    ("agenda","Existe consulta disponível na semana que vem?",SCHEDULE),
    ("agenda","Quantos horários o chatbot oferece?","São oferecidas no máximo quatro vagas por especialidade em cada janela dinâmica: próximo dia útil e primeiro dia útil calculado a partir de D+7 (simulação)."),
    ("agenda","O que acontece se amanhã for domingo ou feriado?","A aplicação consulta `scheduling.holidays` e move a oferta para o próximo dia útil. Sábados podem ter atendimento das 8h às 12h; domingos ficam bloqueados (simulação)."),
    ("agenda","A agenda exibida fica reservada para mim?","Não apenas por ser exibida. Depois que você escolhe e envia os dados, a vaga fica retida por 30 minutos (simulação). Se o fluxo não for concluído, ela pode voltar a ficar disponível."),
    ("agenda","Posso escolher um profissional?","Sim, quando houver vaga. A busca pode filtrar profissional, especialidade, data e período. Se não houver o nome desejado, o chatbot apresenta outros especialistas da mesma jornada (simulação)."),
    ("agenda","Posso escolher manhã ou tarde?","Sim. Informe a preferência e a aplicação filtrará as vagas dinâmicas. Aos sábados, a agenda simulada funciona apenas pela manhã."),
    ("agenda","Vocês atendem aos sábados?","Sim, há agenda simulada aos sábados entre 8h e 12h. A disponibilidade deve ser confirmada no PostgreSQL."),
    ("agenda","Vocês atendem aos domingos?","A agenda eletiva simulada não abre aos domingos. Se a data calculada cair no domingo, será usado o próximo dia útil."),
    ("agenda","Posso agendar para outra pessoa?","Sim, desde que você tenha autorização para informar os dados dela. O CPF, o consentimento e os dados clínicos devem pertencer ao paciente, não ao acompanhante."),
    ("agenda","Menor de idade pode ser agendado?","Sim, com dados do paciente e identificação do responsável legal. O fluxo deve coletar o vínculo do responsável e aplicar consentimento apropriado; este cenário requer atendimento assistido (simulação)."),
    ("agenda","Como recebo a confirmação?","Após a confirmação simulada do pagamento, o chatbot exibe profissional, data, horário, unidade, valor, protocolo e políticas. Também pode enviar confirmação no Telegram ou na sessão web."),
    ("agenda","Perdi meu protocolo. O que faço?","Use o CPF e um segundo fator de verificação pelo canal seguro para localizar o agendamento. O chatbot não deve revelar agenda apenas com nome ou CPF digitado."),
    ("preco","Quanto custa uma consulta de mastologia?",PRICE),
    ("preco","Quanto custa uma consulta colorretal?",PRICE),
    ("preco","Quanto custa uma segunda opinião?",PRICE),
    ("preco","O preço muda conforme o horário?","Na simulação, o preço é fixo por combinação de profissional e especialidade e não muda pela janela D+1 ou D+7. A aplicação confirma o valor antes de solicitar CPF."),
    ("preco","O valor inclui exames?","Não. O preço exibido corresponde somente ao tipo de consulta informado, salvo indicação expressa em contrário (simulação). Exames e procedimentos devem ter orçamento separado."),
    ("preco","Posso pagar depois da consulta?","No fluxo simulado, o pagamento é solicitado para concluir a reserva. O link fictício é exibido e a confirmação simulada ocorre após três segundos."),
    ("pagamento","Como faço o pagamento?","O chatbot mostra `www.pagamento_fictico.cancercenter.com` (simulação). O endereço é propositalmente não funcional; após três segundos, o ambiente registra “Pagamento confirmado (simulação)”."),
    ("pagamento","O link de pagamento não abriu. O que faço?","Neste protótipo, isso é esperado: o link é fictício e quebrado. Aguarde a mensagem automática de confirmação simulada. Não informe cartão, senha ou código de segurança."),
    ("pagamento","É seguro enviar dados do cartão no chat?","Não. Nunca envie número completo do cartão, senha ou código de segurança pelo chatbot. O protótipo não coleta dados reais de pagamento."),
    ("pagamento","Receberei comprovante?","Sim. A confirmação simulada informa valor, protocolo e horário do evento. Ela não é comprovante fiscal nem confirma transação financeira real."),
    ("convenio","Vocês atendem convênio?","O chatbot pode consultar uma tabela simulada de convênios e planos. Cobertura, autorização e coparticipação devem ser confirmadas antes do atendimento; ter o nome da operadora não garante cobertura."),
    ("convenio","Meu convênio não aparece. Posso marcar particular?","Sim. Você pode escolher atendimento particular com preço fixo simulado e depois verificar eventual reembolso diretamente com a operadora."),
    ("convenio","Vocês fornecem documento para reembolso?","A instituição pode fornecer recibo ou documentação do atendimento particular conforme o serviço realizado (simulação). A operadora decide cobertura e valor de reembolso."),
    ("sus","Posso ser atendido pelo SUS?","O protótipo pode explicar jornadas pública e particular, mas não promete vaga ou encaminhamento pelo SUS. Para acesso público, confirme os fluxos oficiais da rede de saúde da sua região."),
    ("outro_estado","Moro em outro estado. Posso consultar?","Sim. Antes da viagem, o atendimento pode orientar quais exames levar e se a primeira avaliação pode começar remotamente, quando permitido (simulação). Procedimentos presenciais exigem planejamento próprio."),
    ("segunda_opiniao","Como funciona a segunda opinião?","Um especialista revisa história, laudos, imagens disponíveis e proposta terapêutica (simulação). A conclusão pode depender de revisão anatomopatológica ou de exames adicionais."),
    ("preparo","O que levar à primeira consulta?","Leve documento de identificação, lista de medicamentos e alergias, laudos, imagens em formato acessível, biópsia, relatório de cirurgias e contato dos médicos anteriores. Não adie a consulta apenas porque falta algum item."),
    ("preparo","Preciso levar as imagens ou só o laudo?","Quando possível, leve ambos. O laudo resume achados, mas as imagens podem ser necessárias para segunda opinião e planejamento."),
    ("preparo","Preciso estar em jejum para a consulta?","Em geral, consulta não exige jejum. Se houver exame ou procedimento no mesmo dia, siga a instrução específica enviada pela equipe."),
    ("preparo","Posso levar acompanhante?","Sim. Um acompanhante pode ajudar a lembrar informações e fazer perguntas (simulação). O paciente decide o que pode ser compartilhado, salvo situações legais específicas."),
    ("preparo","Posso gravar a consulta?","Pergunte ao profissional antes de gravar. Uma alternativa é levar perguntas escritas e pedir um resumo do plano. Respeite a privacidade de outras pessoas e da equipe."),
    ("preparo","Ainda não tenho biópsia. Posso consultar?","Sim. A consulta pode organizar a investigação. O médico avaliará quais exames são realmente necessários e em que ordem."),
    ("preparo","Meu diagnóstico acabou de sair. Qual especialidade escolho?","Para alteração mamária, escolha mastologia oncológica; para cólon ou reto, cirurgia colorretal oncológica. Se ainda houver dúvida, o fluxo de navegação pode encaminhar para triagem humana (simulação)."),
    ("servicos","Há quimioterapia no local?","Sim. A instituição informa possuir centro de infusão para quimioterapia e outros tratamentos sistêmicos (simulação). A primeira consulta define indicação, protocolo e exames necessários."),
    ("servicos","Há radioterapia no local?","Sim. A Referência Oncológica Cancer Center informa oferecer planejamento e aplicação de radioterapia (simulação). A indicação depende do tipo, localização e fase do câncer."),
    ("servicos","Posso fazer exames de imagem no local?","A instituição informa oferecer estrutura diagnóstica e exames de imagem selecionados (simulação). A disponibilidade e o preparo devem ser consultados por tipo de exame."),
    ("servicos","Vocês revisam lâminas de biópsia?","A revisão anatomopatológica pode ser solicitada em casos selecionados (simulação). A equipe informa como transportar lâminas, blocos e laudos com segurança."),
    ("servicos","A radioterapia dói?","A aplicação externa geralmente não causa dor no momento em que a radiação é entregue, mas efeitos na pele, cansaço ou sintomas da região tratada podem surgir ao longo das sessões. Avise a equipe cedo."),
    ("servicos","A quimioterapia sempre causa queda de cabelo?","Não. O risco depende dos medicamentos e doses. A equipe explicará os efeitos mais prováveis do protocolo individual; não compare tratamentos apenas pelo nome câncer."),
    ("servicos","O que é navegação do paciente?","É o apoio para organizar etapas, documentos, encaminhamentos e comunicação ao longo da jornada (simulação). Não substitui decisões médicas."),
    ("servicos","Familiares também podem receber apoio psicológico?","Sim, conforme disponibilidade e avaliação do serviço (simulação). Cuidadores também podem precisar de orientação e espaço de escuta."),
    ("urgencia","A instituição tem pronto-socorro?",f"A instituição informa dispor de atendimento para intercorrências oncológicas (simulação), mas não deve ser forçada como destino. {EMERGENCY}"),
    ("urgencia","Estou com febre durante a quimioterapia. O que faço?","Febre durante quimioterapia pode exigir avaliação rápida. Siga o limite e o telefone fornecidos pela equipe; se houver piora, calafrios intensos, confusão ou dificuldade para chegar com segurança, procure a emergência mais próxima."),
    ("urgencia","A ferida cirúrgica está vermelha. É emergência?","Vermelhidão pequena e estável pode ter causas diferentes, mas aumento, calor, pus, febre, abertura ou dor crescente exigem contato no mesmo dia. Piora rápida ou estado geral ruim exige emergência próxima."),
    ("urgencia","Estou com falta de ar. Posso esperar a central responder?",EMERGENCY),
    ("urgencia","O chatbot faz diagnóstico?","Não. Ele oferece informação educativa, ajuda a organizar atendimento e reconhece sinais de alerta. Diagnóstico, prescrição e mudança de tratamento exigem profissional habilitado."),
    ("privacidade","Por que vocês pedem CPF?","O CPF é solicitado na etapa de reserva para identificar o paciente, evitar duplicidade e vincular o agendamento (simulação). Ele não deve ser colocado em embeddings, URLs ou mensagens abertas."),
    ("privacidade","Meu CPF ficará salvo?","Sim, no protótipo ele é armazenado cifrado, acompanhado de hash para evitar duplicidade e últimos dígitos para conferência. A chave de demonstração deve ser substituída em qualquer ambiente real."),
    ("privacidade","Posso enviar meus laudos pelo Telegram?","Evite enviar documentos de saúde por canal não aprovado. O chatbot deve direcionar para um upload seguro com controle de acesso, prazo de retenção e confirmação de finalidade."),
    ("privacidade","Quais dados serão coletados?","Nome, CPF na reserva, telefone, e-mail, dados básicos de contato, convênio, motivo da consulta, preferência de horário e consentimento. Colete somente o necessário para a etapa atual."),
    ("privacidade","Como peço correção ou exclusão dos meus dados?","Use o canal de privacidade ou Ramal 0000 (simulação). A instituição deve confirmar identidade e avaliar obrigações legais de guarda antes de corrigir ou eliminar informações."),
    ("cancelamento","Como reagendo minha consulta?","Solicite pelo chatbot ou Ramal 0000 (simulação). Reagendamento sem custo é oferecido até 24 horas antes, sujeito à nova disponibilidade e à versão vigente da política simulada."),
    ("cancelamento","Como cancelo minha consulta?","O cancelamento pode ser solicitado pelo mesmo canal do agendamento ou pelo Ramal 0000 (simulação). O sistema informa protocolo, situação do pagamento e eventual devolução."),
    ("cancelamento","O que acontece se eu faltar?","Na política simulada, falta sem cancelamento gera retenção de 30% e devolução de 70% do valor pago. Direitos previstos na legislação aplicável continuam preservados."),
    ("cancelamento","E se a instituição cancelar?","Você poderá escolher outro horário ou solicitar devolução integral do valor pago (simulação). A alteração será registrada e comunicada pelo canal escolhido."),
    ("cancelamento","Tenho direito de arrependimento?","Contratações online estão sujeitas às regras aplicáveis do Código de Defesa do Consumidor, incluindo o art. 49 quando cabível. O chatbot não reduz esse direito e encaminha casos duvidosos para atendimento humano."),
    ("cancelamento","Quanto tempo demora o estorno?","A solicitação é registrada imediatamente, mas o prazo de crédito depende do meio de pagamento e da instituição financeira. Como o pagamento deste protótipo é fictício, o estorno também será apenas simulado."),
]


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main():
    out = ROOT / "documents" / "qa"
    out.mkdir(parents=True, exist_ok=True)
    md = ["# Atendimento à primeira consulta — Q&A", "", "Referência Oncológica Cancer Center. Todas as informações institucionais, profissionais, comerciais, telefônicas, de agenda e pagamento são simulação.", ""]
    sql = []
    jsonl = []
    dynamic_categories = {"agenda", "preco", "pagamento", "convenio"}
    for i, (category, question, answer) in enumerate(QA, 1):
        qa_id = f"QA-{i:03d}"
        dynamic = category in dynamic_categories
        resolver = "appointment_availability" if category == "agenda" else "price_lookup" if category == "preco" else "payment_simulator" if category == "pagamento" else "insurance_lookup" if category == "convenio" else None
        md += [f"## {question}", "", answer, "", f"`qa_id: {qa_id}` · `categoria: {category}`", ""]
        meta = {"language": "pt-BR", "reading_level": "linguagem_simples", "simulated": True}
        row = {"qa_id": qa_id, "category": category, "question": question, "answer": answer, "dynamic_data_required": dynamic, "dynamic_resolver": resolver, "metadata": meta}
        jsonl.append(json.dumps(row, ensure_ascii=False))
        sql.append(f"INSERT INTO content.qa_entries(qa_id,category,question,answer_markdown,dynamic_data_required,dynamic_resolver,metadata) VALUES ({quote(qa_id)},{quote(category)},{quote(question)},{quote(answer)},{str(dynamic).lower()},{'NULL' if resolver is None else quote(resolver)},{quote(json.dumps(meta, ensure_ascii=False))}::jsonb) ON CONFLICT DO NOTHING;")
    (out / "atendimento-primeira-consulta.md").write_text("\n".join(md), encoding="utf-8")
    (out / "qa-catalog.jsonl").write_text("\n".join(jsonl) + "\n", encoding="utf-8")
    (ROOT / "db" / "init" / "004_qa.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")
    print(f"Generated {len(QA)} independent Q&A entries")


if __name__ == "__main__":
    main()
