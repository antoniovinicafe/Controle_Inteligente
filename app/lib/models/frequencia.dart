/// Presença em aulas já encerradas. Aula cancelada ou que ainda não
/// terminou não entra na conta - quem decide isso é o backend.
class Frequencia {
  final int total;
  final int presencas;
  final int faltas;

  /// Null quando ainda não houve nenhuma aula: mostrar "0%" nesse caso
  /// pareceria péssima frequência em vez de "ainda não teve aula".
  final int? percentual;

  const Frequencia({
    required this.total,
    required this.presencas,
    required this.faltas,
    required this.percentual,
  });

  bool get semAulas => total == 0;

  factory Frequencia.fromJson(Map<String, dynamic> json) => Frequencia(
        total: (json['total'] as num).toInt(),
        presencas: (json['presencas'] as num).toInt(),
        faltas: (json['faltas'] as num).toInt(),
        percentual: (json['percentual'] as num?)?.toInt(),
      );
}

/// A frequência de um aluno, do ponto de vista do professor.
class AlunoFrequencia {
  final String id;
  final String nome;
  final String? matricula;

  /// Deduzido do e-mail institucional pelo servidor (gec -> Computação,
  /// get -> Telecomunicações). Null quando o e-mail não é do Inatel.
  /// Ninguém digita isso, então não tem como divergir do cadastro.
  final String? curso;

  final Frequencia frequencia;

  const AlunoFrequencia({
    required this.id,
    required this.nome,
    required this.matricula,
    required this.curso,
    required this.frequencia,
  });

  factory AlunoFrequencia.fromJson(Map<String, dynamic> json) => AlunoFrequencia(
        id: json['id'] as String,
        nome: json['nome'] as String,
        matricula: json['matricula'] as String?,
        curso: json['curso'] as String?,
        frequencia: Frequencia.fromJson(json),
      );
}
