"""Gera Markdown para pacientes e SQL de catálogo parent-child.

O conteúdo é deliberadamente separado em dados estruturados e renderização para
que revisões clínicas possam ser feitas em um único lugar. A saída é determinística.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "documents"
CREATED = "2026-08-08"
REVIEW = "2027-02-08"


BREAST = [
    ("cirurgia-conservadora", "Cirurgia conservadora da mama", "cirurgia", "Cuide da incisão e evite esforço com o braço até a liberação. O resultado das margens pode indicar necessidade de nova cirurgia; isso não significa que houve erro."),
    ("mastectomia-simples", "Mastectomia simples", "cirurgia", "A retirada da mama muda a sensibilidade do tórax. Dormência, repuxamento e diferença de volume podem ocorrer; dor crescente ou abaulamento precisa ser avaliado."),
    ("mastectomia-reconstrucao-imediata", "Mastectomia com reconstrução imediata", "cirurgia", "Observe tanto a ferida quanto a pele reconstruída. Mudança súbita de cor, pele muito fria, escura ou pálida exige contato imediato com a equipe."),
    ("linfonodo-sentinela", "Biópsia do linfonodo sentinela", "cirurgia", "Pode haver coloração azulada temporária da pele ou urina quando corante é utilizado. Inchaço persistente do braço deve ser comunicado."),
    ("esvaziamento-axilar", "Esvaziamento axilar", "cirurgia", "Há maior risco de rigidez do ombro e linfedema. Faça apenas os exercícios ensinados e proteja a pele do braço operado de cortes e queimaduras."),
    ("protese-expansor", "Reconstrução com prótese ou expansor", "cirurgia", "O expansor pode causar pressão durante os preenchimentos. Vermelhidão progressiva, abertura da ferida ou exposição do implante são alertas."),
    ("reconstrucao-retalho", "Reconstrução da mama com retalho", "cirurgia", "Existem duas áreas de recuperação: mama e região doadora. Evite comprimir o retalho e siga a postura orientada pela cirurgia plástica."),
    ("dreno-cirurgico", "Cuidados com dreno após cirurgia da mama", "cirurgia", "Mantenha o reservatório abaixo da ferida, anote volume e aparência no mesmo horário e não corte nem empurre o tubo. Saída acidental requer contato com a equipe."),
    ("seroma-ferida", "Seroma e cuidados com a ferida da mama", "pos_operatorio", "Uma bolsa de líquido pode formar abaulamento e sensação de movimento. Não tente furar ou esvaziar em casa; a equipe decidirá se precisa drenar."),
    ("linfedema-prevencao", "Prevenção e reconhecimento do linfedema", "reabilitacao", "Peso, aperto, diferença de tamanho ou dificuldade com anéis e mangas merecem avaliação precoce. Não faça automassagem forte sem orientação."),
    ("retorno-atividades", "Retorno às atividades após cirurgia da mama", "reabilitacao", "O retorno é gradual. Dirigir exige movimento seguro, ausência de sedação e capacidade de frear sem dor. Carga e academia dependem da liberação da equipe."),
    ("anatomopatologico", "Consulta do resultado anatomopatológico da mama", "seguimento", "O laudo informa tipo, tamanho, margens, linfonodos e biomarcadores. Nenhum item isolado define todo o tratamento; leve o laudo completo à consulta."),
    ("pre-quimioterapia", "Antes de cada sessão de quimioterapia para câncer de mama", "pre_quimioterapia", "Confirme exames e relate febre, infecção, uso de antibiótico, gravidez possível e novos remédios. Não esconda sintomas por medo de adiar a sessão."),
    ("pos-quimioterapia", "Depois da quimioterapia para câncer de mama", "pos_quimioterapia", "Tenha termômetro e telefones à mão. Febre durante quimioterapia pode ser urgência; não tome antitérmico para mascará-la antes de falar com a equipe."),
    ("regime-ac", "Doxorrubicina e ciclofosfamida — orientação ao paciente", "quimioterapia", "A urina pode ficar avermelhada por curto período após doxorrubicina. Isso difere de sangue persistente. Febre, falta de ar ou palpitação requerem avaliação."),
    ("paclitaxel", "Paclitaxel — orientação ao paciente", "quimioterapia", "Avise imediatamente sobre falta de ar, coceira ou aperto durante a infusão. Formigamento e perda de sensibilidade devem ser relatados antes do ciclo seguinte."),
    ("trastuzumabe", "Trastuzumabe — orientação ao paciente", "terapia_alvo", "A equipe pode acompanhar a função do coração. Falta de ar nova, inchaço nas pernas, ganho rápido de peso ou palpitações precisam ser comunicados."),
    ("planejamento-radioterapia", "Planejamento da radioterapia da mama", "pre_radioterapia", "Na simulação, a posição e as marcações ajudam a repetir o tratamento com precisão. Não apague marcas e não aplique produtos antes da sessão sem autorização."),
    ("durante-radioterapia", "Cuidados durante a radioterapia da mama", "radioterapia", "Lave a pele com suavidade, evite calor, atrito e sol na área. Use somente hidratantes e desodorantes autorizados pela equipe."),
    ("apos-radioterapia", "Cuidados após radioterapia da mama", "pos_radioterapia", "A reação da pele pode piorar por alguns dias depois da última sessão. Proteção solar e hidratação orientada continuam importantes."),
    ("mamografia-ultrassom", "Preparo para mamografia e ultrassom das mamas", "imagem", "Leve exames anteriores. No dia da mamografia, evite cosméticos na mama e axila se o serviço orientar; avise sobre cirurgia recente e dor."),
    ("ressonancia-contraste", "Ressonância das mamas com contraste", "imagem", "Informe gravidez possível, implantes, dispositivos, alergias e doença renal. Retire objetos metálicos conforme orientação do serviço."),
    ("sexualidade", "Sexualidade após tratamento do câncer de mama", "qualidade_de_vida", "Desejo, conforto e imagem corporal podem mudar. Retome intimidade no seu ritmo; dor, secura ou sofrimento persistente podem ser tratados."),
    ("fertilidade", "Fertilidade e tratamento do câncer de mama", "qualidade_de_vida", "Converse antes de iniciar terapia sistêmica quando houver desejo reprodutivo. Não interrompa tratamento hormonal e não tente engravidar sem orientação oncológica."),
    ("menopausa", "Sintomas de menopausa durante o tratamento da mama", "qualidade_de_vida", "Ondas de calor, secura e alteração do sono podem ocorrer. Não use hormônios, fitoterápicos ou suplementos sem discutir com a oncologia."),
    ("imagem-corporal", "Imagem corporal e adaptação após cirurgia da mama", "psicossocial", "Não existe um prazo correto para aceitar mudanças. Prótese externa, reconstrução, roupas adaptadas e apoio psicológico são escolhas pessoais."),
    ("apoio-emocional", "Apoio emocional no câncer de mama", "psicossocial", "Medo e tristeza podem aparecer. Procure ajuda se houver sofrimento intenso, isolamento, desesperança ou pensamentos de se machucar; risco imediato exige emergência."),
    ("idosa-fragil-gestante-pcd", "Alertas especiais no tratamento do câncer de mama", "populacoes_especiais", "Pessoas frágeis, gestantes e pessoas com deficiência podem precisar de plano adaptado, acompanhante, acessibilidade e revisão de medicamentos."),
]

COLORECTAL = [
    ("colectomia-direita", "Colectomia direita", "cirurgia", "É comum o intestino funcionar mais vezes ou com fezes amolecidas no início. Incapacidade de beber, distensão crescente ou ausência de gases com vômitos são alertas."),
    ("colectomia-esquerda", "Colectomia esquerda", "cirurgia", "A função intestinal pode oscilar. Não use laxantes ou antidiarreicos por conta própria no pós-operatório recente."),
    ("sigmoidectomia", "Sigmoidectomia", "cirurgia", "Dor deve melhorar gradualmente. Febre, dor crescente, barriga endurecida ou secreção pela ferida podem indicar complicação e exigem avaliação."),
    ("ressecao-anterior-reto", "Ressecção anterior do reto", "cirurgia", "Evacuações frequentes, urgência e fragmentação podem ocorrer. Registre sintomas e alimentação para a equipe orientar reabilitação intestinal."),
    ("amputacao-abdominoperineal", "Amputação abdominoperineal", "cirurgia", "Há recuperação abdominal, perineal e adaptação à colostomia definitiva. Evite pressão prolongada sobre a ferida do períneo conforme orientação."),
    ("ileostomia", "Cuidados com ileostomia", "estomia", "A saída costuma ser líquida. Meça volume quando orientado e observe sede, pouca urina, tontura e boca seca, pois podem indicar desidratação."),
    ("colostomia", "Cuidados com colostomia", "estomia", "O estoma deve estar úmido e rosado ou avermelhado. Cor escura, sangramento persistente, dor forte ou ausência de eliminação com sintomas exigem avaliação."),
    ("reversao-estomia", "Reversão de ileostomia ou colostomia", "cirurgia", "O intestino pode levar semanas para encontrar novo ritmo. Proteja a pele ao redor do ânus e siga a progressão alimentar indicada."),
    ("cirurgia-laparoscopica", "Cirurgia colorretal laparoscópica", "cirurgia", "Pequenas incisões não significam pequena cirurgia interna. Respeite restrições de esforço e os sinais de alerta da cirurgia abdominal."),
    ("cirurgia-robotica", "Cirurgia colorretal robótica", "cirurgia", "A tecnologia auxilia o cirurgião, mas os cuidados com alimentação, feridas, trombose e função intestinal continuam necessários."),
    ("ferida-dreno", "Ferida e dreno após cirurgia colorretal", "pos_operatorio", "Anote o débito do dreno sem manipular a entrada. Se sair, não reinsira. Secreção com mau cheiro, pus ou aumento súbito merece contato."),
    ("alimentacao-posop", "Alimentação após cirurgia colorretal", "pos_operatorio", "Faça a progressão indicada, mastigue bem e hidrate-se. Não existe uma dieta única: estomia, extensão da cirurgia e sintomas mudam a orientação."),
    ("trombose-mobilizacao", "Mobilização e prevenção de trombose após cirurgia colorretal", "pos_operatorio", "Caminhadas curtas e frequentes ajudam quando liberadas. Dor ou inchaço em uma perna, dor no peito ou falta de ar são urgências."),
    ("pre-quimioterapia", "Antes da quimioterapia para câncer colorretal", "pre_quimioterapia", "Informe diarreia, vômitos, formigamento, febre e redução da urina. Exames podem levar a ajuste ou adiamento seguro do ciclo."),
    ("pos-quimioterapia", "Depois da quimioterapia para câncer colorretal", "pos_quimioterapia", "Monitore febre, hidratação e evacuações. Diarreia intensa, sangue, tontura ou incapacidade de beber exigem contato rápido."),
    ("folfox", "FOLFOX — orientação ao paciente", "quimioterapia", "Oxaliplatina pode causar sensibilidade ao frio e formigamento; fluorouracila pode causar diarreia e feridas na boca. Evite frio conforme orientação."),
    ("capox", "CAPOX — orientação ao paciente", "quimioterapia", "Capecitabina é tomada em casa e oxaliplatina na infusão. Não dobre doses esquecidas. Vermelhidão dolorosa em mãos e pés deve ser comunicada."),
    ("capecitabina", "Capecitabina em casa", "quimioterapia", "Tome exatamente como prescrito, sem triturar ou compensar dose. Guarde longe de crianças e não compartilhe comprimidos."),
    ("planejamento-radio-reto", "Planejamento da radioterapia do reto", "pre_radioterapia", "Bexiga e intestino podem precisar de preparo reproduzível. Siga exatamente as instruções de água, alimentação e esvaziamento."),
    ("durante-radio-reto", "Durante a radioterapia pélvica", "radioterapia", "Diarreia, ardor ao urinar, cansaço e irritação da pele podem ocorrer. Avise cedo para receber medidas de suporte."),
    ("apos-radio-reto", "Após radioterapia pélvica", "pos_radioterapia", "Alguns sintomas persistem ou pioram brevemente após o fim. Sangramento importante, febre ou desidratação exigem avaliação."),
    ("colonoscopia", "Preparo para colonoscopia", "imagem_endoscopia", "A qualidade do preparo determina a visibilidade. Siga dieta e laxante prescritos; confirme ajustes de anticoagulantes e remédios para diabetes."),
    ("tomografia-contraste", "Tomografia com contraste no câncer colorretal", "imagem", "Informe alergia prévia a contraste, doença renal, gravidez possível e medicamentos. A equipe definirá jejum e hidratação."),
    ("ressonancia-reto", "Ressonância da pelve para câncer de reto", "imagem", "O exame ajuda a planejar o tratamento. Informe dispositivos e dificuldade para ficar deitado; não presuma jejum sem confirmar."),
    ("funcao-intestinal", "Adaptação da função intestinal", "reabilitacao", "Frequência, urgência, gases e escapes podem mudar. Diário intestinal, nutrição e fisioterapia pélvica podem ajudar."),
    ("sexualidade-fertilidade", "Sexualidade e fertilidade no câncer colorretal", "qualidade_de_vida", "Cirurgia e radioterapia pélvica podem afetar função sexual e fertilidade. Converse antes do tratamento quando possível."),
    ("retorno-trabalho", "Retorno ao trabalho após tratamento colorretal", "reabilitacao", "Planeje retorno gradual, acesso a banheiro e pausas. Trabalho físico exige liberação específica para evitar hérnia."),
    ("apoio-emocional", "Apoio emocional no câncer colorretal", "psicossocial", "Estomia e mudanças intestinais podem afetar autonomia e convívio. Psicologia e grupos de apoio podem ajudar paciente e família."),
    ("idoso-fragil-gestante-pcd", "Alertas especiais no tratamento colorretal", "populacoes_especiais", "Fragilidade, gestação, limitações motoras, visuais ou cognitivas exigem adaptações, revisão de remédios e plano de apoio."),
]


COMMON_SECTIONS = [
    ("Para que serve este documento", "Este material ajuda você e sua família a se prepararem, reconhecerem o que costuma acontecer e saberem quando pedir ajuda. Ele complementa — e não substitui — as instruções individualizadas da equipe."),
    ("Antes do procedimento ou sessão", "Confirme data, local, jejum e medicamentos diretamente com a equipe. Leve documento, lista atualizada de remédios, alergias, exames solicitados e contato de quem o acompanhará. Não suspenda anticoagulantes, remédios para diabetes, pressão ou suplementos por conta própria. Avise sobre febre, tosse nova, infecção, gravidez possível, queda recente, dificuldade de locomoção ou mudança importante no estado de saúde."),
    ("Ao chegar em casa", "Use somente os medicamentos prescritos e respeite os horários. Organize água, alimentos tolerados, termômetro e telefones de contato. Nas primeiras horas, tenha um adulto disponível quando houver sedação ou limitação de movimento. Levante devagar e caminhe apenas quando for seguro. Não dirija enquanto estiver com dor limitante, sonolência ou usando medicamento que reduza a atenção."),
    ("Cuidados práticos", "Mantenha curativos limpos e secos pelo tempo orientado. Não aplique álcool, água oxigenada, pomadas, ervas, óleos ou receitas caseiras. Banho, exercícios, alimentação e retorno ao trabalho variam conforme o tratamento; prevalece a orientação recebida na alta. Anote sintomas, temperatura, evacuações, volume de drenos ou estomia quando solicitado."),
    ("O que pode acontecer", "Cansaço, desconforto controlável, mudança de apetite, sono e funcionamento do intestino podem ocorrer. O esperado é haver estabilidade ou melhora gradual. Compare o sintoma com o seu próprio dia anterior, não com a experiência de outra pessoa. Se algo o preocupa, entre em contato mesmo que não apareça nesta lista."),
    ("Quando falar com a equipe no mesmo dia", "Entre em contato no mesmo dia se houver febre conforme o limite fornecido pela equipe, dor que não melhora com a prescrição, vômitos repetidos, diarreia relevante, redução da urina, ferida mais vermelha ou quente, secreção, sangramento persistente, dificuldade para usar medicamentos ou piora em vez de melhora. Ramal 0000 (simulação)."),
    ("Quando procurar emergência", "Procure o serviço de emergência mais próximo se houver falta de ar importante, desmaio, confusão, dor forte no peito, sangramento volumoso, convulsão, reação alérgica com inchaço de rosto ou garganta, fraqueza súbita, incapacidade de acordar normalmente ou piora rápida. Não espere resposta do chatbot e não atravesse a cidade se houver um serviço mais próximo."),
    ("Alertas para situações especiais", "Pessoas idosas ou frágeis podem desidratar e perder autonomia rapidamente. Gestantes ou quem possa estar grávida devem avisar antes de exames e medicamentos. Pessoas com deficiência devem solicitar acessibilidade, acompanhante e instruções no formato adequado. Quem mora sozinho deve combinar uma rede de apoio e um plano para emergências."),
    ("Perguntas para a próxima consulta", "Pergunte qual é o objetivo do tratamento, quais restrições valem para você, quando revisar a ferida ou exames, como receber o resultado, quais sintomas mudam o plano e quem contatar fora do horário. Leve suas anotações e peça que a equipe registre orientações diferentes deste material."),
]


def slug_id(prefix: str, slug: str) -> str:
    return f"{prefix}-{slug.upper().replace('-', '_')}-001"


def yaml_header(doc_id: str, title: str, cancer: str, phase: str, physician: str) -> str:
    return f"""---
document_id: "{doc_id}"
title: "{title}"
version: "0.1.0"
responsible_physician: "{physician}"
created_at: "{CREATED}"
last_reviewed_at: "{CREATED}"
next_review_at: "{REVIEW}"
information_status: "simulação"
---"""


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def generate_family(cancer: str, prefix: str, physician: str, cases: list[tuple[str,str,str,str]]):
    catalog = []
    sql = []
    family_dir = OUT / "clinical" / cancer
    family_dir.mkdir(parents=True, exist_ok=True)
    for slug, title, phase, specific in cases:
        doc_id = slug_id(prefix, slug)
        sections = [COMMON_SECTIONS[0], ("Orientação específica", specific), *COMMON_SECTIONS[1:]]
        body = [yaml_header(doc_id, title, cancer, phase, physician), "", f"# {title}", "", "**Referência Oncológica Cancer Center — conteúdo educativo (simulação).**", ""]
        for heading, text_body in sections:
            body += [f"## {heading}", "", text_body, ""]
        body += ["## Serviços que podem fazer parte do cuidado", "", "Quando houver indicação individual, a Referência Oncológica Cancer Center informa dispor de cirurgia oncológica, quimioterapia, radioterapia, exames, psicologia, nutrição, fisioterapia, cuidados com estomias e discussão multidisciplinar em tumor board (todos os dados institucionais são simulação).", "", "## Fontes de apoio", "", "- Instituto Nacional de Câncer (INCA): materiais de orientação ao paciente.", "- National Cancer Institute (NCI): informações de tratamento para pacientes.", "- A decisão individual pertence à equipe que conhece o caso.", ""]
        path = family_dir / f"{slug}.md"
        path.write_text("\n".join(body), encoding="utf-8")

        metadata = {"cancer_type": cancer, "care_phase": phase, "procedure_slug": slug, "reading_level": "linguagem_simples", "simulated": True}
        catalog.append({"document_id": doc_id, "title": title, "path": str(path.relative_to(ROOT)), "responsible_physician": physician, "version": "0.1.0", "metadata": metadata})
        sql.append(f"INSERT INTO content.documents(document_id,title,document_type,cancer_type,care_phase,procedure_slug,responsible_physician,version,created_at,last_reviewed_at,next_review_at,patient_markdown_path,metadata) VALUES ({sql_quote(doc_id)},{sql_quote(title)},'orientacao_clinica',{sql_quote(cancer)},{sql_quote(phase)},{sql_quote(slug)},{sql_quote(physician)},'0.1.0','{CREATED}','{CREATED}','{REVIEW}',{sql_quote(str(path.relative_to(ROOT)))},{sql_quote(json.dumps(metadata, ensure_ascii=False))}::jsonb) ON CONFLICT DO NOTHING;")
        for idx, (heading, text_body) in enumerate(sections, 1):
            urgency = "emergencia" if heading == "Quando procurar emergência" else "contato_no_mesmo_dia" if heading == "Quando falar com a equipe no mesmo dia" else "educativo"
            chunk_id = f"{doc_id}-C{idx:02d}"
            chunk_meta = {**metadata, "section": heading}
            sql.append(f"INSERT INTO content.chunks(chunk_id,parent_document_id,ordinal,heading,content_markdown,urgency,metadata) VALUES ({sql_quote(chunk_id)},{sql_quote(doc_id)},{idx},{sql_quote(heading)},{sql_quote(text_body)},{sql_quote(urgency)},{sql_quote(json.dumps(chunk_meta, ensure_ascii=False))}::jsonb) ON CONFLICT DO NOTHING;")
    return catalog, sql


def main():
    OUT.mkdir(exist_ok=True)
    breast_catalog, breast_sql = generate_family("mama", "MAMA", "Dra. Fulana Silva", BREAST)
    colorectal_catalog, colorectal_sql = generate_family("colorretal", "COLORRETAL", "Dr. Ciclano Silva", COLORECTAL)
    catalog = breast_catalog + colorectal_catalog
    (OUT / "catalog.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in catalog) + "\n", encoding="utf-8")
    (ROOT / "db" / "init" / "003_content.sql").write_text("\n".join(breast_sql + colorectal_sql) + "\n", encoding="utf-8")
    index = ["# Índice de documentos clínicos", "", f"Total: {len(catalog)} documents parent.", ""]
    for item in catalog:
        index.append(f"- [{item['title']}]({item['path'].removeprefix('documents/')}) — `{item['document_id']}`")
    (OUT / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Generated {len(catalog)} parent documents")


if __name__ == "__main__":
    main()
