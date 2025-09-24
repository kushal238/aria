// lib/screens/home_screen.dart
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:intl/intl.dart';
import 'auth_screen.dart';
import 'prescription_detail_screen.dart';

// TODO: Create and import a prescription detail screen for patients

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final _storage = const FlutterSecureStorage();
  
  List<dynamic> _prescriptions = [];
  bool _isLoading = true;
  String _errorMessage = '';
  Map<String, dynamic>? _userProfile; // To hold the loaded user profile

  @override
  void initState() {
    super.initState();
    _loadUserProfileAndPrescriptions();
  }

  Future<void> _loadUserProfileAndPrescriptions() async {
    await _loadUserProfile();
    _fetchPrescriptions();
  }

  Future<void> _loadUserProfile() async {
    final profileJson = await _storage.read(key: 'user_profile');
    if (profileJson != null) {
      setState(() {
        _userProfile = jsonDecode(profileJson);
      });
    }
  }

  Future<void> _fetchPrescriptions() async {
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });
    
    try {
      final idToken = await _storage.read(key: 'id_token');
      if (idToken == null) throw Exception("Authentication token not found.");

      final url = Uri.parse('https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev/prescriptions');
      final response = await http.get(
        url,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': idToken,
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: const Text('My Prescriptions'),
        automaticallyImplyLeading: false,
        leading: IconButton(
          icon: const Icon(Icons.person_outline),
          onPressed: () => _scaffoldKey.currentState?.openDrawer(),
        ),
      ),
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
            const Spacer(),
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
              ? const Center(
                  child: Text(
                    'You have no prescriptions yet.',
                    style: TextStyle(fontSize: 18, color: Colors.grey),
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
                      final doctorFirstName = prescription['doctorFirstName'] ?? 'Dr.';
                      final doctorLastName = prescription['doctorLastName'] ?? 'Unknown';

                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                        child: ListTile(
                          title: Text("Prescription from $doctorFirstName $doctorLastName"),
                          subtitle: Text("Issued on: $formattedDate"),
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
    );
  }
}