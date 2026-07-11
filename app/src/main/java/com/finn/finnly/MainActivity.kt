package com.finn.finnly

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.finn.finnly.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.tvHello.text = "Hello, Finnly! \uD83D\uDC4B"
    }
}
