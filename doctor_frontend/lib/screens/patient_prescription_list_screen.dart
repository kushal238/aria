import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'prescription_detail_screen.dart';

/// A screen that displays a list of prescriptions for a single, specific patient.
///
/// This widget is stateless because it simply receives and displays the data
/// passed to it, without managing any internal state that changes over time.
class PatientPrescriptionListScreen extends StatelessWidget {
  /// The patient's profile information (e.g., name, ID).
  final Map<String, dynamic> patient;

  /// The list of prescriptions belonging to this patient.
  final List<dynamic> prescriptions;

  const PatientPrescriptionListScreen({
    super.key,
    required this.patient,
    required this.prescriptions,
  });

  @override
  Widget build(BuildContext context) {
    final patientFirstName = patient['first_name'] ?? 'N/A';
    final patientLastName = patient['last_name'] ?? '';
    final patientFullName = '$patientFirstName $patientLastName'.trim();

    return Scaffold(
      appBar: AppBar(
        title: Text('Prescriptions for $patientFullName'),
      ),
      body: ListView.builder(
        itemCount: prescriptions.length,
        itemBuilder: (context, index) {
          final prescription = prescriptions[index];
          final createdAt = DateTime.parse(prescription['createdAt']);
          final formattedDate = DateFormat.yMMMd().format(createdAt);
          final medicationCount = (prescription['medications'] as List).length;
          final status = prescription['status'] ?? 'UNKNOWN';

          return Card(
            margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: ListTile(
              title: Text('Issued on: $formattedDate'),
              subtitle: Text('$medicationCount medication(s) - Status: $status'),
              trailing: const Icon(Icons.arrow_forward_ios),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => PrescriptionDetailScreen(prescription: prescription),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
