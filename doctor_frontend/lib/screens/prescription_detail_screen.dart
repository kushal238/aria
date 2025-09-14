import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class PrescriptionDetailScreen extends StatelessWidget {
  final Map<String, dynamic> prescription;

  const PrescriptionDetailScreen({super.key, required this.prescription});

  @override
  Widget build(BuildContext context) {
    final createdAt = DateTime.parse(prescription['createdAt']);
    final formattedDate = DateFormat.yMMMMd().add_jm().format(createdAt);
    final patientFirstName = prescription['patientFirstName'] ?? 'N/A';
    final patientLastName = prescription['patientLastName'] ?? '';
    final doctorFirstName = prescription['doctorFirstName'] ?? 'Dr.';
    final doctorLastName = prescription['doctorLastName'] ?? 'Unknown';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Prescription Details'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildDetailCard(
              title: 'Patient',
              child: Text('$patientFirstName $patientLastName', style: const TextStyle(fontSize: 18)),
            ),
            const SizedBox(height: 16),
            _buildDetailCard(
              title: 'Prescribed By',
              child: Text('$doctorFirstName $doctorLastName', style: const TextStyle(fontSize: 18)),
            ),
            const SizedBox(height: 16),
            _buildDetailCard(
              title: 'Issued on',
              child: Text(formattedDate, style: const TextStyle(fontSize: 16)),
            ),
            const SizedBox(height: 16),
            if (prescription['diagnosis'] != null)
              _buildDetailCard(
                title: 'Diagnosis',
                child: Text(prescription['diagnosis'], style: const TextStyle(fontSize: 16)),
              ),
            const SizedBox(height: 24),
            Text(
              'Medications',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Divider(),
            ..._buildMedicationList(prescription['medications']),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailCard({required String title, required Widget child}) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: const TextStyle(fontSize: 14, color: Colors.grey),
            ),
            const SizedBox(height: 8),
            child,
          ],
        ),
      ),
    );
  }

  List<Widget> _buildMedicationList(List<dynamic> medications) {
    return medications.map((med) {
      return Card(
        margin: const EdgeInsets.symmetric(vertical: 8.0),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                med['name'],
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              _buildMedicationRow('Dosage:', med['dosage']),
              _buildMedicationRow('Frequency:', med['frequency']),
              _buildMedicationRow('Duration:', med['duration']),
              if (med['instructions'] != null)
                _buildMedicationRow('Instructions:', med['instructions']),
            ],
          ),
        ),
      );
    }).toList();
  }

  Widget _buildMedicationRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value),
        ],
      ),
    );
  }
}
