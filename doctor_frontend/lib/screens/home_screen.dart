// lib/screens/home_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'patient_search_screen.dart'; // Import the new screen
import 'prescription_detail_screen.dart';
import 'auth_screen.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'patient_prescription_list_screen.dart'; // Import the new screen we will create

// A new model class to hold our grouped data, associating a patient
// with their list of prescriptions.
class PatientPrescriptions {
  final Map<String, dynamic> patient;
  final List<dynamic> prescriptions;
  PatientPrescriptions({required this.patient, required this.prescriptions});
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // --- State Variables ---

  // Holds the raw, flat list of all prescriptions fetched from the API.
  List<dynamic> _allPrescriptions = [];
  // Holds the prescriptions grouped by patient. This is our primary data structure.
  List<PatientPrescriptions> _groupedPrescriptions = [];
  // Holds the list of patients currently displayed, after applying the search filter.
  List<PatientPrescriptions> _filteredPrescriptions = [];

  bool _isLoading = true;
  String _errorMessage = '';
  final _storage = const FlutterSecureStorage();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>(); // Add a key for the Scaffold
  Map<String, dynamic>? _userProfile; // To hold the loaded user profile
  // Controller to manage the text input for the search field.
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadUserProfileAndPrescriptions();
    // Add a listener to the search controller
    _searchController.addListener(_filterPatients);
  }

  @override
  void dispose() {
    _searchController.removeListener(_filterPatients);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadUserProfileAndPrescriptions() async {
    await _loadUserProfile();
    await _fetchPrescriptions();
  }

  Future<void> _loadUserProfile() async {
    final profileJson = await _storage.read(key: 'user_profile');
    if (profileJson != null) {
      setState(() {
        _userProfile = jsonDecode(profileJson);
      });
    }
  }

  Future<void> _handleLogout() async {
    try {
      await Amplify.Auth.signOut();
      await _storage.deleteAll();
      if (mounted) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const AuthScreen()),
          (Route<dynamic> route) => false,
        );
      }
    } on AuthException catch (e) {
      if(mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error signing out: ${e.message}'))
        );
      }
    }
  }

  /// Fetches all prescriptions from the backend, then triggers the grouping logic.
  Future<void> _fetchPrescriptions() async {
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });
    
    try {
      final apiToken = await _storage.read(key: 'api_token');
      if (apiToken == null) throw Exception("Authentication token not found.");

      final url = Uri.parse('https://c51qcky1d1.execute-api.us-east-1.amazonaws.com/dev/prescriptions');
      final response = await http.get(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $apiToken',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _allPrescriptions = data;
          // After fetching, process the flat list into a structured, grouped list.
          _groupAndSortPrescriptions();
        });
      } else {
        final errorBody = jsonDecode(response.body);
        throw Exception("Failed to load prescriptions: ${errorBody['detail'] ?? response.body}");
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
      });
    } finally {
      if(mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  /// Processes the flat list of prescriptions (`_allPrescriptions`) and groups them
  /// by patient ID into the `_groupedPrescriptions` list.
  void _groupAndSortPrescriptions() {
    // A map to temporarily hold patients and their prescriptions for efficient lookup.
    final Map<String, PatientPrescriptions> patientMap = {};

    for (var p in _allPrescriptions) {
      final patientId = p['patientId'];
      if (patientId != null) {
        // If we haven't seen this patient yet, create a new entry for them.
        if (!patientMap.containsKey(patientId)) {
          patientMap[patientId] = PatientPrescriptions(
            patient: {
              'internal_user_id': patientId,
              'first_name': p['patientFirstName'],
              'last_name': p['patientLastName'],
            },
            prescriptions: [],
          );
        }
        // Add the current prescription to this patient's list.
        patientMap[patientId]!.prescriptions.add(p);
      }
    }
    // For each patient, sort their prescriptions by date to ensure the newest is always first.
    patientMap.forEach((_, patientData) {
      patientData.prescriptions.sort((a, b) => DateTime.parse(b['createdAt']).compareTo(DateTime.parse(a['createdAt'])));
    });

    // Convert the map of patients into a list.
    final sortedList = patientMap.values.toList()
      // Sort the list of patients so that those with the most recent prescription appear at the top.
      ..sort((a, b) {
        final dateA = DateTime.parse(a.prescriptions.first['createdAt']);
        final dateB = DateTime.parse(b.prescriptions.first['createdAt']);
        return dateB.compareTo(dateA);
      });
      
    setState(() {
      _groupedPrescriptions = sortedList;
      // Apply the initial search filter (which will be empty, showing all patients).
      _filterPatients();
    });
  }

  /// Filters the `_groupedPrescriptions` list based on the current search query
  /// and updates the `_filteredPrescriptions` list which is rendered by the UI.
  void _filterPatients() {
    final query = _searchController.text.toLowerCase();
    setState(() {
      _filteredPrescriptions = _groupedPrescriptions.where((p) {
        final firstName = p.patient['first_name']?.toLowerCase() ?? '';
        final lastName = p.patient['last_name']?.toLowerCase() ?? '';
        // A patient is a match if their first or last name contains the search query.
        return firstName.contains(query) || lastName.contains(query);
      }).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey, // Assign the key to the Scaffold
      appBar: AppBar(
        title: const Text('Doctor Dashboard'),
        automaticallyImplyLeading: false,
        // Add the new profile icon button to open the drawer
        leading: IconButton(
          icon: const Icon(Icons.person_outline),
          onPressed: () {
            _scaffoldKey.currentState?.openDrawer();
          },
        ),
        actions: const [], // Remove the old logout button
      ),
      // Add the Drawer (sidebar)
      drawer: Drawer(
        child: Column(
          children: <Widget>[
            UserAccountsDrawerHeader(
              accountName: Text(
                _userProfile != null
                  ? '${_userProfile!['first_name'] ?? ''} ${_userProfile!['last_name'] ?? ''}'
                  : 'Loading...'
              ),
              accountEmail: Text(_userProfile?['email'] ?? ''),
              currentAccountPicture: CircleAvatar(
                backgroundColor: Colors.white,
                child: Icon(Icons.person, size: 50),
              ),
            ),
            // Add other drawer items here if needed in the future
            const Spacer(), // Pushes the logout button to the bottom
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Log Out'),
              onTap: _handleLogout,
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                labelText: 'Search Patients',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8.0),
                ),
              ),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _errorMessage.isNotEmpty
                    ? Center(child: Text(_errorMessage, style: const TextStyle(color: Colors.red)))
                    : _filteredPrescriptions.isEmpty
                        ? Center(
                            child: Text(
                              _searchController.text.isNotEmpty
                                ? 'No patients found for "${_searchController.text}"'
                                : 'You have not written any prescriptions yet.\nTap the "+" button to write your first one.',
                              style: TextStyle(fontSize: 18, color: Colors.grey[600]),
                              textAlign: TextAlign.center,
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: _fetchPrescriptions,
                            child: ListView.builder(
                              itemCount: _filteredPrescriptions.length,
                              itemBuilder: (context, index) {
                                final patientPrescriptions = _filteredPrescriptions[index];
                                final patient = patientPrescriptions.patient;
                                final patientFirstName = patient['first_name'] ?? 'N/A';
                                final patientLastName = patient['last_name'] ?? '';
                                final patientFullName = '$patientFirstName $patientLastName'.trim();
                                final prescriptionCount = patientPrescriptions.prescriptions.length;

                                return Card(
                                  margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                                  child: ListTile(
                                    title: Text(patientFullName),
                                    subtitle: Text('$prescriptionCount prescription(s)'),
                                    trailing: const Icon(Icons.arrow_forward_ios),
                                    onTap: () async {
                                      // Navigate and check if we need to refresh on return
                                      final result = await Navigator.of(context).push(
                                        MaterialPageRoute(
                                          builder: (context) => PatientPrescriptionListScreen(patient: patient, prescriptions: patientPrescriptions.prescriptions),
                                        ),
                                      );
                                      // If the detail screen pops with 'true', refresh the data
                                      if (result == true) {
                                        _fetchPrescriptions();
                                      }
                                    },
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          // Navigate and wait for a result. If a prescription was created,
          // the form screen can pop 'true' to trigger a refresh.
          final result = await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (context) => const PatientSearchScreen(),
            ),
          );

          if (result == true) {
            _fetchPrescriptions();
          }
        },
        tooltip: 'Write New Prescription',
        child: const Icon(Icons.add),
      ),
    );
  }
}