import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';

import 'package:flutter_typeahead/flutter_typeahead.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';

// Represents a single medication entry in the form
class MedicationController {
  final TextEditingController name;
  final TextEditingController dosage;
  final TextEditingController frequency;
  final TextEditingController duration;
  final TextEditingController instructions;

  MedicationController()
      : name = TextEditingController(),
        dosage = TextEditingController(),
        frequency = TextEditingController(),
        duration = TextEditingController(),
        instructions = TextEditingController();
  
  void dispose() {
    name.dispose();
    dosage.dispose();
    frequency.dispose();
    duration.dispose();
    instructions.dispose();
  }
  
  // Helper to check if a controller group is empty
  bool get isNotEmpty => name.text.isNotEmpty || dosage.text.isNotEmpty || frequency.text.isNotEmpty || duration.text.isNotEmpty;

  // Convert controller data to a map for API submission
  Map<String, dynamic> toMap() {
    return {
      'name': name.text,
      'dosage': dosage.text,
      'frequency': frequency.text,
      'duration': duration.text,
      'instructions': instructions.text.isEmpty ? null : instructions.text,
    };
  }
}

class PrescriptionFormScreen extends StatefulWidget {
  final Map<String, dynamic> patient; // TODO: Replace with a strong User model

  const PrescriptionFormScreen({super.key, required this.patient});

  @override
  State<PrescriptionFormScreen> createState() => _PrescriptionFormScreenState();
}

class _PrescriptionFormScreenState extends State<PrescriptionFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _diagnosisController = TextEditingController();
  final _expiresAtController = TextEditingController();
  final List<MedicationController> _medicationControllers = [];
  
  bool _isLoading = false;
  final _storage = const FlutterSecureStorage();
  final String _apiBase = 'https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev';

  @override
  void initState() {
    super.initState();
    // Start with one empty medication form
    _addMedication();
  }

  @override
  void dispose() {
    _diagnosisController.dispose();
    _expiresAtController.dispose();
    for (var controller in _medicationControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  void _addMedication() {
    setState(() {
      _medicationControllers.add(MedicationController());
    });
  }

  void _removeMedication(int index) {
    setState(() {
      _medicationControllers[index].dispose();
      _medicationControllers.removeAt(index);
    });
  }
  
  Future<void> _submitPrescription() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() { _isLoading = true; });

    try {
      final apiToken = await _storage.read(key: 'api_token');
      if (apiToken == null) throw Exception("Authentication token not found.");
      
      final medicationsPayload = _medicationControllers
          .where((c) => c.isNotEmpty) // Filter out empty medication forms
          .map((c) => c.toMap())
          .toList();

      if (medicationsPayload.isEmpty) {
        throw Exception("At least one medication is required.");
      }

      final body = jsonEncode({
        'patientId': widget.patient['internal_user_id'],
        'expiresAt': _expiresAtController.text,
        'diagnosis': _diagnosisController.text.isEmpty ? null : _diagnosisController.text,
        'medications': medicationsPayload,
      });

      final response = await http.post(
        Uri.parse('https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev/prescriptions'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $apiToken',
        },
        body: body,
      );

      if (response.statusCode == 201) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Prescription created successfully!'), backgroundColor: Colors.green),
        );
        // Pop twice to go back to the home screen (past the patient search screen)
        // The first pop dismisses the form screen and sends 'true' back to the search screen
        Navigator.of(context).pop(true);
      } else {
         final errorBody = jsonDecode(response.body);
         throw Exception("Failed to create prescription: ${errorBody['detail'] ?? response.body}");
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      if(mounted) {
        setState(() { _isLoading = false; });
      }
    }
  }

  // --- Typeahead: call backend /drugs/search ---
  Future<List<Map<String, dynamic>>> _searchDrugs(String pattern) async {
    final query = pattern.trim();
    if (query.length < 2) return [];
    try {
      String? idToken = await _storage.read(key: 'id_token');
      if (idToken == null || idToken.isEmpty) {
        debugPrint('Typeahead: id_token missing in storage, fetching from Amplify session...');
        final session = await Amplify.Auth.fetchAuthSession();
        if (session is CognitoAuthSession) {
          idToken = session.userPoolTokensResult.value.idToken.raw;
          await _storage.write(key: 'id_token', value: idToken);
        }
      }
      if (idToken == null || idToken.isEmpty) {
        debugPrint('Typeahead: no id_token available, aborting search');
        return [];
      }
      final uri = Uri.parse('$_apiBase/drugs/search?q=${Uri.encodeQueryComponent(query)}&limit=10');
      final resp = await http.get(
        uri,
        headers: { 'Authorization': 'Bearer $idToken' },
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final items = (data['items'] as List<dynamic>? ?? []).cast<Map<String, dynamic>>();
        return items;
      } else {
        debugPrint('Typeahead: backend ${resp.statusCode} body=${resp.body}');
      }
    } catch (e) {
      debugPrint('Typeahead error: $e');
    }
    return [];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('New Prescription for ${widget.patient['first_name']}'),
      ),
      body: Form(
        key: _formKey,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextFormField(
                controller: _diagnosisController,
                decoration: const InputDecoration(
                  labelText: 'Diagnosis',
                  border: OutlineInputBorder(),
                ),
                textCapitalization: TextCapitalization.sentences,
                maxLines: 3,
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: _expiresAtController,
                readOnly: true,
                decoration: const InputDecoration(
                  labelText: 'Prescription Expires At',
                  border: OutlineInputBorder(),
                  suffixIcon: Icon(Icons.calendar_today),
                ),
                onTap: () async {
                  final DateTime? picked = await showDatePicker(
                    context: context,
                    initialDate: DateTime.now().add(const Duration(days: 7)),
                    firstDate: DateTime.now(),
                    lastDate: DateTime.now().add(const Duration(days: 365)),
                  );
                  if (picked != null) {
                    // Format the date to yyyy-MM-dd
                    _expiresAtController.text = DateFormat('yyyy-MM-dd').format(picked);
                  }
                },
                validator: (value) => value == null || value.isEmpty ? 'Please select an expiry date' : null,
              ),
              const SizedBox(height: 30),
              const Text('Medications', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const Divider(),
              ..._buildMedicationForms(),
              const SizedBox(height: 20),
              TextButton.icon(
                icon: const Icon(Icons.add),
                label: const Text('Add Another Medication'),
                onPressed: _addMedication,
              ),
              const SizedBox(height: 40),
              _isLoading
                ? const Center(child: CircularProgressIndicator())
                : ElevatedButton(
                    onPressed: _submitPrescription,
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                      textStyle: const TextStyle(fontSize: 18),
                    ),
                    child: const Text('Submit Prescription'),
                  ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildMedicationForms() {
    return _medicationControllers.asMap().entries.map((entry) {
      int index = entry.key;
      MedicationController controller = entry.value;
      return Card(
        margin: const EdgeInsets.symmetric(vertical: 8.0),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Medication #${index + 1}', style: const TextStyle(fontWeight: FontWeight.bold)),
                  if (_medicationControllers.length > 1)
                    IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.red),
                      onPressed: () => _removeMedication(index),
                    ),
                ],
              ),
              const SizedBox(height: 10),
              TypeAheadField<Map<String, dynamic>>(
                suggestionsCallback: (pattern) => _searchDrugs(pattern),
                builder: (context, textController, focusNode) {
                  // Keep controllers in sync so typing triggers searches
                  textController.text = controller.name.text;
                  textController.selection = TextSelection.fromPosition(TextPosition(offset: textController.text.length));
                  return TextFormField(
                    controller: textController,
                    focusNode: focusNode,
                    onChanged: (v) => controller.name.text = v,
                    decoration: const InputDecoration(labelText: 'Medication Name (type to search)'),
                    validator: (value) => controller.isNotEmpty && (value == null || value.isEmpty) ? 'Name is required' : null,
                  );
                },
                itemBuilder: (context, suggestion) {
                  return ListTile(
                    title: Text(
                      suggestion['brand_name']?.toString() ?? '',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text('Code: ${suggestion['identifier']}'),
                  );
                },
                onSelected: (suggestion) {
                  controller.name.text = suggestion['brand_name']?.toString() ?? '';
                },
                emptyBuilder: (context) => const Padding(
                  padding: EdgeInsets.all(12.0),
                  child: Text('No matches. You can enter free text.'),
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: controller.dosage,
                      decoration: const InputDecoration(labelText: 'Dosage (e.g., 500mg)'),
                      validator: (value) => controller.isNotEmpty && (value == null || value.isEmpty) ? 'Dosage is required' : null,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextFormField(
                      controller: controller.frequency,
                      decoration: const InputDecoration(labelText: 'Frequency (e.g., 1-0-1)'),
                      validator: (value) => controller.isNotEmpty && (value == null || value.isEmpty) ? 'Frequency is required' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: controller.duration,
                decoration: const InputDecoration(labelText: 'Duration (e.g., 7 days)'),
                validator: (value) => controller.isNotEmpty && (value == null || value.isEmpty) ? 'Duration is required' : null,
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: controller.instructions,
                decoration: const InputDecoration(labelText: 'Instructions (e.g., After food)'),
              ),
            ],
          ),
        ),
      );
    }).toList();
  }
}
