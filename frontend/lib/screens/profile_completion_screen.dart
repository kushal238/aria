import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl_phone_field/intl_phone_field.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'home_screen.dart';
import 'auth_screen.dart';

class ProfileCompletionScreen extends StatefulWidget {
  const ProfileCompletionScreen({super.key});

  @override
  State<ProfileCompletionScreen> createState() => _ProfileCompletionScreenState();
}

class _ProfileCompletionScreenState extends State<ProfileCompletionScreen> {
  final _formKey = GlobalKey<FormState>(); // Key for validating the form
  final _firstNameController = TextEditingController();
  final _middleNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _abhaIdController = TextEditingController();
  String _fullPhoneNumber = ''; // To store the complete phone number
  // --- Add New Controllers ---
  final _dateOfBirthController = TextEditingController();
  final _sexController = TextEditingController();
  final _genderController = TextEditingController();
  final _bloodTypeController = TextEditingController();
  // -------------------------
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
    _abhaIdController.dispose();
    // --- Dispose New Controllers ---
    _dateOfBirthController.dispose();
    _sexController.dispose();
    _genderController.dispose();
    _bloodTypeController.dispose();
    // ---------------------------
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
        // Email or phone number might come from Cognito and don't count as a completed profile.
        final hasBasicData = (userData['first_name'] != null && userData['first_name'].isNotEmpty) ||
                            (userData['last_name'] != null && userData['last_name'].isNotEmpty);
        
        // Pre-populate common fields with existing user data
        _firstNameController.text = userData['first_name'] ?? '';
        _middleNameController.text = userData['middle_name'] ?? '';
        _lastNameController.text = userData['last_name'] ?? '';
        _emailController.text = userData['email'] ?? '';
        _abhaIdController.text = userData['abha_id'] ?? '';
        _fullPhoneNumber = userData['phone_number'] ?? '';
        
        // Pre-populate patient-specific fields if they exist
        final patientProfile = userData['patient_profile'];
        if (patientProfile != null) {
          _dateOfBirthController.text = patientProfile['date_of_birth'] ?? '';
          _sexController.text = patientProfile['sex_assigned_at_birth'] ?? '';
          _genderController.text = patientProfile['gender_identity'] ?? '';
          _bloodTypeController.text = patientProfile['blood_type'] ?? '';
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
        profileData['abha_id'] = _abhaIdController.text.trim().isEmpty ? null : _abhaIdController.text.trim();
        profileData['phone_number'] = _fullPhoneNumber.trim().isEmpty ? null : _fullPhoneNumber.trim();
      }
      
      // Always include patient-specific fields
      profileData['date_of_birth'] = _dateOfBirthController.text.trim().isEmpty ? null : _dateOfBirthController.text.trim();
      profileData['sex_assigned_at_birth'] = _sexController.text.trim().isEmpty ? null : _sexController.text.trim();
      profileData['gender_identity'] = _genderController.text.trim().isEmpty ? null : _genderController.text.trim();
      profileData['blood_type'] = _bloodTypeController.text.trim().isEmpty ? null : _bloodTypeController.text.trim();

      // 3. Prepare the request
      final url = Uri.parse('https://c51qcky1d1.execute-api.us-east-1.amazonaws.com/dev/users/complete-profile');

      final headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $apiToken', // Send the final api_token
      };

      final body = jsonEncode(profileData);

      print("Calling complete profile endpoint...");
      print("Headers: $headers"); // Don't log sensitive tokens in production
      print("Body: $body");

      // 4. Make the API call
      final response = await http.post(url, headers: headers, body: body);

      print('Backend Response Status: ${response.statusCode}');
      print('Backend Response Body: ${response.body}');

      // 5. Handle the response
      if (response.statusCode == 200 && mounted) {
        // The backend returns the updated user profile, we don't need to do anything with it here
        // besides confirming success.

        // Navigate to the main app screen (replace with your actual home screen)
        // Use pushAndRemoveUntil to clear the auth flow screens
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (context) => const HomeScreen()),
          (Route<dynamic> route) => false, // Remove all routes below
        );
        return; // Exit function after navigation
        
      } else {
        // Handle backend error (e.g., validation failed, server error)
         String errorMessage = "Profile completion failed (${response.statusCode})";
         try {
             final errorBody = jsonDecode(response.body);
             errorMessage = "Profile completion failed: ${errorBody['detail'] ?? response.body}";
         } catch (_) {
             // Ignore decoding error, use default message
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
        title: const Text('Complete Your Profile'),
        // Add a custom leading back button that triggers logout
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _handleLogout,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Form(
          key: _formKey, // Assign the key to the Form
          child: SingleChildScrollView( // Use SingleChildScrollView to ensure the form is scrollable
            child: Column( // Use Column inside the scroll view
              children: [
                Text(
                  _hasExistingData 
                    ? "Complete your patient profile with the information below."
                    : "Please complete your profile to get started.",
                  style: const TextStyle(fontSize: 16),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 10),
                Text(
                  _hasExistingData
                    ? "Your basic information is pre-filled. Please complete the patient-specific details."
                    : "Please fill in your basic information and patient-specific details.",
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
                const SizedBox(height: 20),
                TextFormField(
                  controller: _abhaIdController,
                  enabled: !_hasExistingData, // Editable for new users, read-only for existing
                  decoration: InputDecoration(
                    labelText: 'ABHA ID (Optional)',
                    border: const OutlineInputBorder(),
                    suffixIcon: _hasExistingData && _abhaIdController.text.isNotEmpty
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 30),
                // --- Patient-Specific Fields Section ---
                const Text(
                  "Patient-Specific Information",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                const Text(
                  "Please complete the following patient-specific details:",
                  style: TextStyle(fontSize: 14, color: Colors.grey),
                ),
                const SizedBox(height: 20),
                // --- Add New Form Fields ---
                TextFormField(
                  controller: _dateOfBirthController,
                  readOnly: true, // Make field read-only
                  decoration: const InputDecoration(
                    labelText: 'Date of Birth',
                    border: OutlineInputBorder(),
                    suffixIcon: Icon(Icons.calendar_today), // Add calendar icon
                  ),
                  onTap: () async {
                    // Hide keyboard
                    FocusScope.of(context).requestFocus(FocusNode());
                    // Show date picker
                    final DateTime? picked = await showDatePicker(
                      context: context,
                      initialDate: DateTime.now(),
                      firstDate: DateTime(1900),
                      lastDate: DateTime.now(),
                    );
                    if (picked != null) {
                      // Format date as YYYY-MM-DD
                      String formattedDate = "${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}";
                      setState(() {
                        _dateOfBirthController.text = formattedDate;
                      });
                    }
                  },
                ),
                const SizedBox(height: 20),
                // --- Sex Dropdown ---
                DropdownButtonFormField<String>(
                  value: _sexController.text.isNotEmpty ? _sexController.text : null,
                  decoration: const InputDecoration(
                    labelText: 'Sex Assigned at Birth',
                    border: OutlineInputBorder(),
                  ),
                  items: ['Female', 'Male', 'Intersex', 'Prefer not to say']
                      .map((label) => DropdownMenuItem(
                            child: Text(label),
                            value: label,
                          ))
                      .toList(),
                  onChanged: (value) {
                    setState(() {
                      _sexController.text = value ?? '';
                    });
                  },
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please select an option';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                // --- Gender Dropdown ---
                DropdownButtonFormField<String>(
                  value: _genderController.text.isNotEmpty ? _genderController.text : null,
                  decoration: const InputDecoration(
                    labelText: 'Gender Identity (Optional)',
                    border: OutlineInputBorder(),
                  ),
                  items: ['Woman', 'Man', 'Transgender', 'Non-binary', 'Prefer not to say']
                      .map((label) => DropdownMenuItem(
                            child: Text(label),
                            value: label,
                          ))
                      .toList(),
                  onChanged: (value) {
                    setState(() {
                      _genderController.text = value ?? '';
                    });
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _bloodTypeController,
                  decoration: const InputDecoration(
                    labelText: 'Blood Type (e.g., A+, O-)',
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
                      child: const Text('Complete Sign Up'),
                    ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}