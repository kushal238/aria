import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'prescription_form_screen.dart';

// TODO: Import the User model and API service
// import '../models/user.dart';
// import '../services/api_service.dart';

class PatientSearchScreen extends StatefulWidget {
  const PatientSearchScreen({super.key});

  @override
  State<PatientSearchScreen> createState() => _PatientSearchScreenState();
}

class _PatientSearchScreenState extends State<PatientSearchScreen> {
  final TextEditingController _searchController = TextEditingController();
  List<dynamic> _searchResults = []; // TODO: Replace dynamic with a User model
  bool _isLoading = false;
  String _errorMessage = '';
  final _storage = const FlutterSecureStorage();

  Future<void> _searchPatients(String query) async {
    if (query.length < 2) { // To avoid spamming the API on every keystroke
      setState(() {
        _searchResults = [];
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final idToken = await _storage.read(key: 'id_token');
      if (idToken == null) throw Exception("Authentication token not found.");

      final url = Uri.parse('https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev/users/search?q=$query');
      
      final response = await http.get(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': idToken,
        },
      );

      if (response.statusCode == 200) {
        final results = jsonDecode(response.body);
        setState(() {
          _searchResults = results;
        });
      } else {
        final errorBody = jsonDecode(response.body);
        throw Exception("Failed to search patients: ${errorBody['detail'] ?? response.body}");
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }
  
  void _onPatientSelected(dynamic patient) async {
    // Navigate and wait for a result from the form screen
    final result = await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => PrescriptionFormScreen(patient: patient),
      ),
    );

    // If the form screen popped 'true', it means a prescription was created.
    // We then pop the search screen with 'true' as well to signal the home screen to refresh.
    if (result == true && mounted) {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Find Patient'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: TextField(
              controller: _searchController,
              autofocus: true,
              decoration: InputDecoration(
                hintText: 'Search by patient name...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onChanged: _searchPatients,
            ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: Center(child: CircularProgressIndicator()),
            ),
          if (_errorMessage.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Text(
                _errorMessage,
                style: const TextStyle(color: Colors.red),
                textAlign: TextAlign.center,
              ),
            ),
          Expanded(
            child: _searchResults.isEmpty && !_isLoading && _searchController.text.isNotEmpty
              ? const Center(child: Text('No patients found.'))
              : ListView.builder(
                  itemCount: _searchResults.length,
                  itemBuilder: (context, index) {
                    final patient = _searchResults[index];
                    return ListTile(
                      title: Text('${patient['first_name']} ${patient['last_name']}'),
                      subtitle: Text(patient['email'] ?? ''),
                      onTap: () => _onPatientSelected(patient),
                    );
                  },
                ),
          ),
        ],
      ),
    );
  }
}
