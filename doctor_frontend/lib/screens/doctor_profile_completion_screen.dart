import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl_phone_field/intl_phone_field.dart';
import 'package:amplify_flutter/amplify_flutter.dart';

// TODO: Import your actual main app screen (e.g., home_screen.dart)
import 'home_screen.dart';
import 'auth_screen.dart';

class DoctorProfileCompletionScreen extends StatefulWidget {
  const DoctorProfileCompletionScreen({super.key});

  @override
  State<DoctorProfileCompletionScreen> createState() => _DoctorProfileCompletionScreenState();
}

class _DoctorProfileCompletionScreenState extends State<DoctorProfileCompletionScreen> {
  final _formKey = GlobalKey<FormState>(); // Key for validating the form
  final _firstNameController = TextEditingController();
  final _middleNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _emailController = TextEditingController();
  String _fullPhoneNumber = ''; // To store the complete phone number

  // --- Doctor-Specific Controllers ---
  final _licenseNumberController = TextEditingController();
  final _specializationController = TextEditingController();
  final _qualificationsController = TextEditingController();
  final _clinicAddressController = TextEditingController();
  // ------------------------------------

  final _storage = const FlutterSecureStorage(); // Secure storage instance

  bool _isLoading = false;
  bool _isInitialized = false;
  bool _hasExistingData = false; // Track if user has existing data

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
  }

  @override
  void dispose() {
    // Dispose controllers when the widget is removed from the widget tree
    _firstNameController.dispose();
    _middleNameController.dispose();
    _lastNameController.dispose();
    _emailController.dispose();

    // --- Dispose Doctor Controllers ---
    _licenseNumberController.dispose();
    _specializationController.dispose();
    _qualificationsController.dispose();
    _clinicAddressController.dispose();
    // ---------------------------------
    super.dispose();
  }

  Future<void> _loadUserProfile() async {
    try {
      final apiToken = await _storage.read(key: 'api_token');
      if (apiToken == null) {
        throw Exception("Authentication token not found. Please log in again.");
      }

      final url = Uri.parse('https://c51qcky1d1.execute-api.us-east-1.amazonaws.com/dev/users/me');
      final headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $apiToken',
      };

      final response = await http.get(url, headers: headers);
      
      if (response.statusCode == 200) {
        final userData = jsonDecode(response.body);
        
        // Corrected Logic: A user has existing data only if they have a first or last name.
        final hasBasicData = (userData['first_name'] != null && userData['first_name'].isNotEmpty) ||
                            (userData['last_name'] != null && userData['last_name'].isNotEmpty);
        
        // Pre-populate common fields with existing user data
        _firstNameController.text = userData['first_name'] ?? '';
        _middleNameController.text = userData['middle_name'] ?? '';
        _lastNameController.text = userData['last_name'] ?? '';
        _emailController.text = userData['email'] ?? '';
        _fullPhoneNumber = userData['phone_number'] ?? '';
        
        // Pre-populate doctor-specific fields if they exist
        final doctorProfile = userData['doctor_profile'];
        if (doctorProfile != null) {
          _licenseNumberController.text = doctorProfile['license_number'] ?? '';
          _specializationController.text = doctorProfile['specialization'] ?? '';
          _qualificationsController.text = doctorProfile['qualifications']?.join(', ') ?? '';
          _clinicAddressController.text = doctorProfile['clinic_address'] ?? '';
        }
        
        setState(() {
          _isInitialized = true;
          _hasExistingData = hasBasicData;
        });
      } else {
        throw Exception("Failed to load user profile: ${response.statusCode}");
      }
    } catch (e) {
      print("Error loading user profile: $e");
      // Still show the form, but without pre-populated data
      setState(() {
        _isInitialized = true;
      });
    }
  }

  Future<void> _submitProfile() async {
    // Validate the form first
    if (!_formKey.currentState!.validate()) {
      return; // If validation fails, do nothing
    }

    setState(() { _isLoading = true; });

    try {
      // 1. Retrieve the final api_token saved after login
      final apiToken = await _storage.read(key: 'api_token');
      if (apiToken == null) {
        throw Exception("Authentication token not found. Please log in again.");
      }

      // 2. Prepare the data payload
      final profileData = <String, dynamic>{};
      
      // For new users, include basic information
      if (!_hasExistingData) {
        profileData['first_name'] = _firstNameController.text.trim();
        profileData['middle_name'] = _middleNameController.text.trim().isEmpty ? null : _middleNameController.text.trim();
        profileData['last_name'] = _lastNameController.text.trim();
        profileData['email'] = _emailController.text.trim().isEmpty ? null : _emailController.text.trim();
        profileData['phone_number'] = _fullPhoneNumber.trim().isEmpty ? null : _fullPhoneNumber.trim();
      }
      
      // Always include doctor-specific fields
      profileData['license_number'] = _licenseNumberController.text.trim();
      profileData['specialization'] = _specializationController.text.trim();
      profileData['qualifications'] = _qualificationsController.text.trim().split(',').map((q) => q.trim()).toList();
      profileData['clinic_address'] = _clinicAddressController.text.trim();

      // 3. Prepare the request
      final url = Uri.parse('https://c51qcky1d1.execute-api.us-east-1.amazonaws.com/dev/users/complete-profile');

      final headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $apiToken', // Send the final api_token
      };

      final body = jsonEncode(profileData);

      print("Calling complete profile endpoint for doctor...");
      print("Headers: $headers");
      print("Body: $body");

      // 4. Make the API call
      final response = await http.post(url, headers: headers, body: body);

      print('Backend Response Status: ${response.statusCode}');
      print('Backend Response Body: ${response.body}');

      // 5. Handle the response
      if (response.statusCode == 200 && mounted) {
        // Navigate to the main app screen
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const HomeScreen()),
          (Route<dynamic> route) => false,
        );
        return;
        
      } else {
        // Handle backend error
         String errorMessage = "Profile completion failed (${response.statusCode})";
         try {
             final errorBody = jsonDecode(response.body);
             errorMessage = "Profile completion failed: ${errorBody['detail'] ?? response.body}";
         } catch (_) {
             // Ignore decoding error
         }
         throw Exception(errorMessage);
      }

    } catch (e) {
       print("Error submitting profile: $e");
       if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
             SnackBar(content: Text('Error: $e')));
       }
    } finally {
       if (mounted) {
          setState(() { _isLoading = false; });
       }
    }
  }

  Future<void> _handleLogout() async {
    try {
      // Sign out from Cognito
      await Amplify.Auth.signOut();
      
      // Clear local secure storage
      await _storage.deleteAll();

      if (mounted) {
        // Navigate back to the Auth screen by popping the current screen
        Navigator.of(context).pop();
      }
    } on AuthException catch (e) {
      print('Error signing out: ${e.message}');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error signing out: ${e.message}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_isInitialized) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Complete Doctor Profile'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _handleLogout,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              children: [
                Text(
                  _hasExistingData 
                    ? "Complete your doctor profile with the information below."
                    : "Please complete your doctor profile to get started.",
                  style: const TextStyle(fontSize: 16),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 10),
                Text(
                  _hasExistingData
                    ? "Your basic information is pre-filled. Please complete the doctor-specific details."
                    : "Please fill in your basic information and doctor-specific details.",
                  style: const TextStyle(fontSize: 14, color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 30),
                TextFormField(
                  controller: _firstNameController,
                  enabled: !_hasExistingData, // Editable for new users, read-only for existing
                  decoration: InputDecoration(
                    labelText: 'First Name',
                    border: const OutlineInputBorder(),
                    suffixIcon: _hasExistingData && _firstNameController.text.isNotEmpty
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
                  ),
                  validator: _hasExistingData ? null : (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your first name';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _middleNameController,
                  enabled: !_hasExistingData, // Editable for new users, read-only for existing
                  decoration: InputDecoration(
                    labelText: 'Middle Name (Optional)',
                    border: const OutlineInputBorder(),
                    suffixIcon: _hasExistingData && _middleNameController.text.isNotEmpty
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
                  ),
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _lastNameController,
                  enabled: !_hasExistingData, // Editable for new users, read-only for existing
                  decoration: InputDecoration(
                    labelText: 'Last Name',
                    border: const OutlineInputBorder(),
                    suffixIcon: _hasExistingData && _lastNameController.text.isNotEmpty
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
                  ),
                  validator: _hasExistingData ? null : (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your last name';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _emailController,
                  enabled: !_hasExistingData, // Editable for new users, read-only for existing
                  decoration: InputDecoration(
                    labelText: 'Email (Optional)',
                    border: const OutlineInputBorder(),
                    suffixIcon: _hasExistingData && _emailController.text.isNotEmpty
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
                  ),
                  keyboardType: TextInputType.emailAddress,
                  validator: _hasExistingData ? null : (value) {
                    if (value != null && value.isNotEmpty && !value.contains('@')) {
                      return 'Please enter a valid email address';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                // --- Phone Number Field ---
                _hasExistingData 
                  ? TextFormField(
                      initialValue: _fullPhoneNumber,
                      enabled: false,
                      decoration: const InputDecoration(
                        labelText: 'Phone Number',
                        border: OutlineInputBorder(),
                        suffixIcon: Icon(Icons.check_circle, color: Colors.green),
                      ),
                    )
                  : IntlPhoneField(
                      decoration: const InputDecoration(
                        labelText: 'Phone Number',
                        border: OutlineInputBorder(),
                      ),
                      initialCountryCode: 'IN',
                      onChanged: (phone) {
                        setState(() {
                          _fullPhoneNumber = phone.completeNumber;
                        });
                      },
                    ),
                const SizedBox(height: 30),
                // --- Doctor-Specific Fields Section ---
                const Text(
                  "Doctor-Specific Information",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                const Text(
                  "Please complete the following doctor-specific details:",
                  style: TextStyle(fontSize: 14, color: Colors.grey),
                ),
                const SizedBox(height: 20),
                // --- Doctor-Specific Fields ---
                TextFormField(
                  controller: _licenseNumberController,
                  decoration: const InputDecoration(
                    labelText: 'Medical License Number',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your license number';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _specializationController,
                  decoration: const InputDecoration(
                    labelText: 'Specialization',
                    border: OutlineInputBorder(),
                  ),
                   validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your specialization';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _qualificationsController,
                  decoration: const InputDecoration(
                    labelText: 'Qualifications (comma-separated)',
                    border: OutlineInputBorder(),
                  ),
                   validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your qualifications';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _clinicAddressController,
                  decoration: const InputDecoration(
                    labelText: 'Clinic Address',
                    border: OutlineInputBorder(),
                  ),
                ),
                // ---------------------------
                const SizedBox(height: 40),
                _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : ElevatedButton(
                      onPressed: _submitProfile,
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 50),
                        textStyle: const TextStyle(fontSize: 18)
                      ),
                      child: const Text('Submit Profile'),
                    ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}