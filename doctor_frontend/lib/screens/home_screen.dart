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

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<dynamic> _prescriptions = [];
  bool _isLoading = true;
  String _errorMessage = '';
  final _storage = const FlutterSecureStorage();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>(); // Add a key for the Scaffold
  Map<String, dynamic>? _userProfile; // To hold the loaded user profile

  @override
  void initState() {
    super.initState();
    _loadUserProfileAndPrescriptions();
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
          _prescriptions = data;
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
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage.isNotEmpty
            ? Center(child: Text(_errorMessage, style: const TextStyle(color: Colors.red)))
            : _prescriptions.isEmpty
              ? Center(
                  child: Text(
                    'You have not written any prescriptions yet.\n\nTap the "+" button to write your first one.',
                    style: TextStyle(fontSize: 18, color: Colors.grey[600]),
                    textAlign: TextAlign.center,
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _fetchPrescriptions,
                  child: ListView.builder(
                    itemCount: _prescriptions.length,
                    itemBuilder: (context, index) {
                      final prescription = _prescriptions[index];
                      final createdAt = DateTime.parse(prescription['createdAt']);
                      final formattedDate = DateFormat.yMMMd().format(createdAt);
                      final medicationCount = (prescription['medications'] as List).length;
                      final patientFirstName = prescription['patientFirstName'] ?? 'N/A';
                      final patientLastName = prescription['patientLastName'] ?? '';

                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                        child: ListTile(
                          title: Text("For Patient: $patientFirstName $patientLastName"),
                          subtitle: Text("$formattedDate - $medicationCount medication(s)"),
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