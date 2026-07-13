package com.finn.finnly

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import androidx.recyclerview.widget.LinearLayoutManager
import com.finn.finnly.data.FeedRepository
import com.finn.finnly.data.db.FeedDatabase
import com.finn.finnly.databinding.ActivityMainBinding
import com.finn.finnly.ui.FeedAdapter
import com.finn.finnly.ui.FeedViewModel
import com.google.android.material.tabs.TabLayout

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var viewModel: FeedViewModel
    private val adapter = FeedAdapter()

    private val tabs = listOf("all" to "全部", "society" to "社会", "economy" to "经济", "entertainment" to "娱乐")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val dao = FeedDatabase.get(this).feedDao()
        viewModel = ViewModelProvider(this)[FeedViewModel::class.java]
        viewModel.init(FeedRepository(dao))

        binding.recyclerView.layoutManager = LinearLayoutManager(this)
        binding.recyclerView.adapter = adapter

        tabs.forEach { (key, label) ->
            val tab = binding.tabLayout.newTab().setText(label)
            tab.tag = key
            binding.tabLayout.addTab(tab)
        }
        binding.tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                viewModel.setFilter(tab.tag as String)
            }
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })

        binding.swipeRefresh.setOnRefreshListener { viewModel.refresh() }

        viewModel.feed.observe(this) { items ->
            adapter.submitList(items)
        }
        viewModel.loading.observe(this) { isLoading ->
            binding.swipeRefresh.isRefreshing = isLoading
        }
        viewModel.error.observe(this) { msg ->
            if (msg != null) binding.toolbar.subtitle = msg
            else binding.toolbar.subtitle = null
        }

        viewModel.refresh()
    }
}
