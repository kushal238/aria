import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl_phone_field/intl_phone_field.dart';

// TODO: Import your actual main app screen (e.g., home_screen.dart)
import 'home_screen.dart';

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
      final profileData = {
        'first_name': _firstNameController.text.trim(),
        'middle_name': _middleNameController.text.trim().isEmpty ? null : _middleNameController.text.trim(),
        'last_name': _lastNameController.text.trim(),
        // Send null if optional fields are empty, adjust if backend expects empty strings
        'email': _emailController.text.trim().isEmpty ? null : _emailController.text.trim(),
        'abha_id': _abhaIdController.text.trim().isEmpty ? null : _abhaIdController.text.trim(),
        'phone_number': _fullPhoneNumber.trim().isEmpty ? null : _fullPhoneNumber.trim(),
        // --- Add New Patient-Specific Fields ---
        'date_of_birth': _dateOfBirthController.text.trim().isEmpty ? null : _dateOfBirthController.text.trim(),
        'sex_assigned_at_birth': _sexController.text.trim().isEmpty ? null : _sexController.text.trim(),
        'gender_identity': _genderController.text.trim().isEmpty ? null : _genderController.text.trim(),
        'blood_type': _bloodTypeController.text.trim().isEmpty ? null : _bloodTypeController.text.trim(),
        // ------------------------------------
      };

      // 3. Prepare the request
      final url = Uri.parse('https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev/users/complete-profile');

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Complete Your Profile'),
        automaticallyImplyLeading: false, // Prevent back button to OTP screen
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Form(
          key: _formKey, // Assign the key to the Form
          child: SingleChildScrollView( // Use SingleChildScrollView to ensure the form is scrollable
            child: Column( // Use Column inside the scroll view
              children: [
                const Text(
                  "Please enter your details to complete sign up.",
                  style: TextStyle(fontSize: 16),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 30),
                TextFormField(
                  controller: _firstNameController,
                  decoration: const InputDecoration(
                    labelText: 'First Name',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) { // Basic validation
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your first name';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),

                TextFormField(
                  controller: _middleNameController,
                  decoration: const InputDecoration(
                    labelText: 'Middle Name (Optional)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 20),

                TextFormField(
                  controller: _lastNameController,
                  decoration: const InputDecoration(
                    labelText: 'Last Name',
                    border: OutlineInputBorder(),
                  ),
                   validator: (value) { // Basic validation
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter your last name';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _emailController,
                  decoration: const InputDecoration(
                    labelText: 'Email (Optional)',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  // Add email validation if needed
                  validator: (value) {
                    if (value != null && value.isNotEmpty && !value.contains('@')) {
                      return 'Please enter a valid email address';
                    }
                    return null; // No error if empty or valid
                  },
                ),
                const SizedBox(height: 20),
                // --- Phone Number Field ---
                IntlPhoneField(
                  decoration: const InputDecoration(
                    labelText: 'Phone Number',
                    border: OutlineInputBorder(),
                  ),
                  initialCountryCode: 'IN', // Set initial country
                  onChanged: (phone) {
                    setState(() {
                      _fullPhoneNumber = phone.completeNumber; // Store the complete number
                    });
                  },
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _abhaIdController,
                  decoration: const InputDecoration(
                    labelText: 'ABHA ID (Optional)',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.number, // Adjust if needed
                  // Add ABHA ID specific validation if needed
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