import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';

import 'package:flutter_typeahead/flutter_typeahead.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/scheduler.dart';

// Represents a single medication entry in the form
class MedicationController {
  final TextEditingController name;
  final TextEditingController dosage;
  final TextEditingController frequency;
  final TextEditingController duration;
  final TextEditingController instructions;

  // Drug coding (from Aurora search)
  String? system; // e.g., http://snomed.info/sct
  String? code;   // identifier as string
  String? display; // brand_name
  String? originalInput; // what doctor had typed
  bool selected; // whether a suggestion was chosen (sticky until edit)

  MedicationController()
      : name = TextEditingController(),
        dosage = TextEditingController(),
        frequency = TextEditingController(),
        duration = TextEditingController(),
        instructions = TextEditingController(),
        system = null,
        code = null,
        display = null,
        originalInput = null,
        selected = false;
  
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
    // If a mapped selection exists, use it; otherwise treat as free text
    final bool mapped = (code != null && code!.isNotEmpty);
    final String resolvedSystem = mapped ? (system ?? 'http://snomed.info/sct') : 'UNMAPPED';
    final String resolvedCode = mapped ? code! : 'UNMAPPED';
    final String resolvedDisplay = mapped ? (display ?? name.text) : name.text;
    final String? resolvedOriginal = originalInput ?? (mapped ? name.text : name.text);
    return {
      // SNOMED fields + original input for backend
      'system': resolvedSystem,
      'code': resolvedCode,
      'display': resolvedDisplay,
      'original_input': resolvedOriginal,
      // legacy/free-text name retained for UI; backend can ignore if using display
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
      // Use Cognito ID token for all API calls (API Gateway authorizer expects it)
      String? idToken = await _storage.read(key: 'id_token');
      if (idToken == null || idToken.isEmpty) {
        final session = await Amplify.Auth.fetchAuthSession();
        if (session is CognitoAuthSession) {
          idToken = session.userPoolTokensResult.value.idToken.raw;
          await _storage.write(key: 'id_token', value: idToken);
        }
      }
      if (idToken == null || idToken.isEmpty) throw Exception("Authentication token not found.");
      
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
          'Authorization': 'Bearer $idToken',
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
                debounceDuration: const Duration(milliseconds: 300),
                suggestionsCallback: (pattern) => controller.selected ? Future.value([]) : _searchDrugs(pattern),
                builder: (context, textController, focusNode) {
                  // Keep controllers in sync so typing triggers searches
                  textController.text = controller.name.text;
                  textController.selection = TextSelection.fromPosition(TextPosition(offset: textController.text.length));
                  return TextFormField(
                    controller: textController,
                    focusNode: focusNode,
                    onChanged: (v) {
                      controller.name.text = v;
                      // Any manual edit unlocks searching again
                      controller.selected = false;
                    },
                    decoration: const InputDecoration(labelText: 'Medication Name (type to search)'),
                    validator: (value) => controller.isNotEmpty && (value == null || value.isEmpty) ? 'Name is required' : null,
                  );
                },
                loadingBuilder: (context) => const Padding(
                  padding: EdgeInsets.all(8.0),
                  child: SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                ),
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
                  final before = controller.name.text;
                  final selected = suggestion['brand_name']?.toString() ?? '';
                  controller.name.text = selected;
                  // Capture coding fields for backend payload
                  controller.system = 'http://snomed.info/sct';
                  final ident = suggestion['identifier'];
                  controller.code = ident == null ? null : ident.toString();
                  controller.display = selected;
                  controller.originalInput = before.isEmpty ? selected : before;
                  controller.selected = true; // lock suggestions until user edits
                  // Trigger rebuild after the current frame to avoid setState during build
                  // and let the internal textController sync from controller.name
                  if (mounted) {
                    SchedulerBinding.instance.addPostFrameCallback((_) {
                      if (mounted) setState(() {});
                    });
                  }
                },
                emptyBuilder: (context) {
                  // After a suggestion is selected, suppress the empty suggestion box entirely
                  if (controller.selected) return const SizedBox.shrink();
                  return const Padding(
                    padding: EdgeInsets.all(12.0),
                    child: Text('Enter medicine name'),
                  );
                },
              ),
              if (controller.code != null && controller.code!.isNotEmpty) ...[
                const SizedBox(height: 6),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Code: ${controller.code}', style: const TextStyle(fontSize: 12, color: Colors.black54)),
                ),
              ],
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
