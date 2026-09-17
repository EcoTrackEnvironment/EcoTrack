import "../styles/Exportacao.css";

import { FaShieldAlt, FaFilePdf, FaFileCsv, FaBuilding } from "react-icons/fa";

import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

function Exportacao() {

    const gerarRelatorioPDF = () => {
        const doc = new jsPDF();

        const dataAtual = new Date().toLocaleDateString("pt-BR");

        // CABEÇALHO

        doc.setFont("helvetica", "bold");
        doc.setFontSize(20);
        doc.text("MOTIVA", 105, 20, { align: "center" });

        doc.setFontSize(14);
        doc.text(
            "RELATÓRIO DE EXECUÇÃO E CONTROLE DOS SERVIÇOS DE ROÇADA",
            105,
            30,
            { align: "center" }
        );

        doc.setFont("helvetica", "normal");
        doc.setFontSize(10);
        doc.text(
            "Modelo de apresentação à ARTESP",
            105,
            38,
            { align: "center" }
        );

        // IDENTIFICAÇÃO

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("IDENTIFICAÇÃO DO RELATÓRIO", 14, 52);

        autoTable(doc, {
            startY: 57,
            theme: "grid",
            styles: {
                fontSize: 9,
                cellPadding: 4
            },
            headStyles: {
                fontStyle: "bold"
            },
            columnStyles: {
                0: { cellWidth: 55 },
                1: { cellWidth: 125 }
            },
            body: [
                ["Concessionária", "Motiva"],
                ["Rodovia(s)", "SP-XXX / SP-XXX"],
                ["Trecho / Lote", "Trecho / Lote de concessão"],
                ["Período de referência", "MM/AAAA"],
                ["Contrato / Instrumento", "Número do contrato"],
                ["Responsável técnico", "Nome / Cargo"],
                ["Data de emissão", dataAtual],
                ["Versão do relatório", "01"]
            ]
        });

        // OBJETIVO

        let y = doc.lastAutoTable.finalY + 12;

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("1. OBJETIVO", 14, y);

        y += 7;

        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");

        const objetivo =
            "Este relatório tem por objetivo registrar e demonstrar a execução, " +
            "o acompanhamento e o controle dos serviços de roçada e conservação " +
            "do revestimento vegetal realizados no período de referência, no âmbito " +
            "da faixa de domínio da rodovia sob responsabilidade da Motiva.";

        const objetivoLinhas = doc.splitTextToSize(objetivo, 180);

        doc.text(objetivoLinhas, 14, y);

        y += objetivoLinhas.length * 5 + 8;

        // RESUMO EXECUTIVO

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("2. RESUMO EXECUTIVO DOS SERVIÇOS", 14, y);

        y += 5;

        autoTable(doc, {
            startY: y,
            theme: "grid",
            styles: {
                fontSize: 8,
                cellPadding: 3
            },
            head: [
                [
                    "Indicador",
                    "Programado",
                    "Executado",
                    "Saldo",
                    "% Execução",
                    "Observação"
                ]
            ],
            body: [
                ["Roçada mecanizada", "-", "-", "-", "-", "-"],
                ["Roçada manual", "-", "-", "-", "-", "-"],
                ["Refilamento/acabamento", "-", "-", "-", "-", "-"],
                ["Aceiros", "-", "-", "-", "-", "-"],
                ["Áreas especiais", "-", "-", "-", "-", "-"]
            ]
        });

        // PROGRAMACAO X EXECUÇÃO

        y = doc.lastAutoTable.finalY + 12;

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("3. PROGRAMAÇÃO E EXECUÇÃO POR TRECHO", 14, y);

        y += 5;

        autoTable(doc, {
            startY: y,
            theme: "grid",
            styles: {
                fontSize: 7,
                cellPadding: 2
            },
            head: [
                [
                    "Data",
                    "Rodovia",
                    "Km inicial",
                    "Km final",
                    "Lado",
                    "Serviço",
                    "Método",
                    "Extensão",
                    "Equipe",
                    "Status"
                ]
            ],
            body: [
                [
                    dataAtual,
                    "SP-XXX",
                    "000+000",
                    "000+000",
                    "Direito",
                    "Roçada",
                    "Mecanizada",
                    "0 km",
                    "Equipe 01",
                    "Concluído"
                ],
                [
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-"
                ],
                [
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-"
                ]
            ]
        });

        // CONTROLE DE QUALIDADE

        y = doc.lastAutoTable.finalY + 12;

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("4. CONTROLE DE QUALIDADE", 14, y);

        y += 8;

        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");

        const controles = [
            "Vegetação mantida dentro do padrão definido para o trecho.",
            "Serviço executado na largura/área prevista.",
            "Acabamento realizado junto aos dispositivos aplicáveis.",
            "Material resultante da roçada tratado conforme procedimento.",
            "Condições de segurança viária observadas.",
            "Sinalização temporária implantada quando exigida.",
            "Interferências com drenagem e sinalização verificadas."
        ];

        controles.forEach((item) => {
            doc.text("☐ " + item, 18, y);
            y += 6;
        });

        // NÃO CONFORMIDADES

        y += 5;

        if (y > 260) {
            doc.addPage();
            y = 20;
        }

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("5. NÃO CONFORMIDADES E AÇÕES CORRETIVAS", 14, y);

        y += 5;

        autoTable(doc, {
            startY: y,
            theme: "grid",
            styles: {
                fontSize: 7,
                cellPadding: 3
            },
            head: [
                [
                    "Data",
                    "Rodovia",
                    "Km",
                    "Descrição",
                    "Classificação",
                    "Ação",
                    "Prazo",
                    "Situação"
                ]
            ],
            body: [
                ["-", "-", "-", "-", "-", "-", "-", "-"],
                ["-", "-", "-", "-", "-", "-", "-", "-"],
                ["-", "-", "-", "-", "-", "-", "-", "-"]
            ]
        });

        // evidências

        y = doc.lastAutoTable.finalY + 12;

        if (y > 250) {
            doc.addPage();
            y = 20;
        }

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("6. EVIDÊNCIAS FOTOGRÁFICAS E GEOREFERENCIADAS", 14, y);

        y += 7;

        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");

        doc.text(
            "As evidências fotográficas deverão apresentar, quando disponível, " +
            "data, rodovia, km, sentido/lado e coordenadas geográficas.",
            14,
            y,
            {
                maxWidth: 180
            }
        );

        y += 12;

        autoTable(doc, {
            startY: y,
            theme: "grid",
            styles: {
                fontSize: 8,
                cellPadding: 3
            },
            head: [
                [
                    "Foto",
                    "Data",
                    "Rodovia",
                    "Km / Coordenadas",
                    "Descrição"
                ]
            ],
            body: [
                ["Foto 01", dataAtual, "SP-XXX", "-", "Registro da roçada"],
                ["Foto 02", "-", "-", "-", "-"],
                ["Foto 03", "-", "-", "-", "-"]
            ]
        });

        // equipamentos

        y = doc.lastAutoTable.finalY + 12;

        if (y > 250) {
            doc.addPage();
            y = 20;
        }

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("7. EQUIPAMENTOS E EQUIPES EMPREGADAS", 14, y);

        y += 5;

        autoTable(doc, {
            startY: y,
            theme: "grid",
            styles: {
                fontSize: 8,
                cellPadding: 3
            },
            head: [
                [
                    "Data",
                    "Equipe",
                    "Equipamento",
                    "Identificação",
                    "Horário",
                    "Responsável"
                ]
            ],
            body: [
                [dataAtual, "Equipe 01", "Roçadeira", "-", "-", "-"],
                ["-", "-", "-", "-", "-", "-"]
            ]
        });

        // conclusão

        y = doc.lastAutoTable.finalY + 12;

        if (y > 245) {
            doc.addPage();
            y = 20;
        }

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("8. CONCLUSÃO", 14, y);

        y += 7;

        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");

        const conclusao =
            "No período de referência, os serviços de roçada e conservação " +
            "do revestimento vegetal foram acompanhados conforme a programação " +
            "apresentada neste relatório. Os trechos atendidos, eventuais pendências " +
            "e ações corretivas encontram-se registrados nas tabelas e evidências.";

        const conclusaoLinhas = doc.splitTextToSize(conclusao, 180);

        doc.text(conclusaoLinhas, 14, y);

        // anexos

        y += conclusaoLinhas.length * 5 + 12;

        doc.setFontSize(14);
        doc.setFont("helvetica", "bold");
        doc.text("9. ANEXOS", 14, y);

        y += 7;

        doc.setFontSize(9);
        doc.setFont("helvetica", "normal");

        [
            "Anexo I – Mapa dos trechos atendidos.",
            "Anexo II – Relatório fotográfico.",
            "Anexo III – Registros georreferenciados.",
            "Anexo IV – Programação x execução detalhada.",
            "Anexo V – Registros de não conformidades."
        ].forEach((item) => {
            doc.text("• " + item, 18, y);
            y += 6;
        });

        // rodapé

        const paginas = doc.getNumberOfPages();

        for (let i = 1; i <= paginas; i++) {
            doc.setPage(i);

            doc.setFontSize(8);
            doc.setFont("helvetica", "normal");

            doc.text(
                "MOTIVA | Relatório de Execução e Controle dos Serviços de Roçada",
                14,
                290
            );

            doc.text(
                `Página ${i} de ${paginas}`,
                196,
                290,
                { align: "right" }
            );
        }

        //download

        doc.save(
            `Relatorio_Rocada_Motiva_ARTESP_${dataAtual.replaceAll("/", "-")}.pdf`
        );
    };


    const exportarCSV = () => {
        console.log("Exportando histórico CSV...");
    };


    const gerarCompliance = () => {
        gerarRelatorioPDF();
    };


    return (
        <div className="container-card-exportacao">

            <div className="titulo-exportacao">
                <FaShieldAlt className="icone-titulo-exportacao" />
                <span>Exportação e Conformidade</span>
            </div>

            <div className="botoes-exportacao">

                <button
                    className="btn-exportacao btn-outline"
                    onClick={gerarRelatorioPDF}
                >
                    <FaFilePdf className="icone-btn" />
                    Gerar Formulário Unifilar de Roçada (PDF)
                </button>

                <button
                    className="btn-exportacao btn-outline"
                    onClick={exportarCSV}
                >
                    <FaFileCsv className="icone-btn" />
                    Exportar Histórico (CSV)
                </button>

                <button
                    className="btn-exportacao btn-filled"
                    onClick={gerarCompliance}
                >
                    <FaBuilding className="icone-btn" />
                    Relatório de Compliance ANTT/ARTESP
                </button>

            </div>

        </div>
    );
}

export default Exportacao;