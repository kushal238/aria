import 'package:flutter/material.dart';
import 'package:amplify_flutter/amplify_flutter.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmationCodeController = TextEditingController();

  bool _isLoading = false;
  bool _codeSent = false; // To switch between UI states
  String _userEmail = '';

  @override
  void dispose() {
    _emailController.dispose();
    _newPasswordController.dispose();
    _confirmationCodeController.dispose();
    super.dispose();
  }

  Future<void> _sendResetCode() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
    });

    final email = _emailController.text.trim();

    try {
      final result = await Amplify.Auth.resetPassword(username: email);
      setState(() {
        _isLoading = false;
        _codeSent = true;
        _userEmail = email;
      });
      _showInfoSnackbar('Confirmation code sent to $email.');
    } on AuthException catch (e) {
      _showErrorSnackbar(e.message);
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _confirmNewPassword() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
    });

    try {
      await Amplify.Auth.confirmResetPassword(
        username: _userEmail,
        newPassword: _newPasswordController.text,
        confirmationCode: _confirmationCodeController.text.trim(),
      );
      _showInfoSnackbar('Password successfully reset! Please sign in.');
      if (mounted) {
        Navigator.of(context).pop(); // Go back to the sign in screen
      }
    } on AuthException catch (e) {
      _showErrorSnackbar(e.message);
      setState(() {
        _isLoading = false;
      });
    }
  }

  void _showErrorSnackbar(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context).removeCurrentSnackBar();
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message), backgroundColor: Colors.redAccent));
    }
  }

  void _showInfoSnackbar(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context).removeCurrentSnackBar();
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset Password')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Form(
          key: _formKey,
          child: _codeSent ? _buildConfirmationForm() : _buildEmailForm(),
        ),
      ),
    );
  }

  Widget _buildEmailForm() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text(
          'Enter your email address to receive a password reset code.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 20),
        TextFormField(
          controller: _emailController,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(
            labelText: 'Email',
            border: OutlineInputBorder(),
          ),
          validator: (value) {
            if (value == null || !value.contains('@')) {
              return 'Please enter a valid email.';
            }
            return null;
          },
        ),
        const SizedBox(height: 20),
        _isLoading
            ? const CircularProgressIndicator()
            : ElevatedButton(
                onPressed: _sendResetCode,
                child: const Text('Send Code'),
              ),
      ],
    );
  }

  Widget _buildConfirmationForm() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          'Enter the code sent to $_userEmail and your new password.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 20),
        TextFormField(
          controller: _confirmationCodeController,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Confirmation Code',
            border: OutlineInputBorder(),
          ),
          validator: (value) {
            if (value == null || value.length < 6) {
              return 'Please enter a valid code.';
            }
            return null;
          },
        ),
        const SizedBox(height: 20),
        TextFormField(
          controller: _newPasswordController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'New Password',
            border: OutlineInputBorder(),
          ),
          validator: (value) {
            if (value == null || value.length < 8) {
              return 'Password must be at least 8 characters.';
            }
            return null;
          },
        ),
        const SizedBox(height: 20),
        _isLoading
            ? const CircularProgressIndicator()
            : ElevatedButton(
                onPressed: _confirmNewPassword,
                child: const Text('Reset Password'),
              ),
      ],
    );
  }
}
